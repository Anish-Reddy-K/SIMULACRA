"""The persistent worker process: claims leased batches and runs them via handlers."""

import asyncio
import contextlib
import logging
import os
import signal
import uuid
from collections.abc import Callable

from sqlalchemy.orm import Session

from simulacra.jobs import queue
from simulacra.jobs.handlers import BatchContext, Handler
from simulacra.jobs.resources import ResourceGuard
from simulacra.persistence.models import WorkerRow

log = logging.getLogger("simulacra.worker")


class Worker:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        handlers: dict[str, Handler],
        worker_id: str | None = None,
        lease_s: float = 30.0,
        poll_s: float = 0.5,
        grace_s: float = 20.0,
        guard: ResourceGuard | None = None,
    ) -> None:
        self.guard = guard
        self.session_factory = session_factory
        self.handlers = handlers
        self.worker_id = worker_id or f"w-{os.getpid()}-{uuid.uuid4().hex[:6]}"
        self.lease_s = lease_s
        self.poll_s = poll_s
        self.grace_s = grace_s
        self.stop = asyncio.Event()

    def _register(self) -> None:
        with self.session_factory() as s:
            s.add(
                WorkerRow(
                    id=self.worker_id,
                    pid=os.getpid(),
                    started_at=queue.now(),
                    heartbeat_at=queue.now(),
                    stopped=False,
                )
            )
            s.commit()

    def _beat(self, stopped: bool = False) -> None:
        with self.session_factory() as s:
            row = s.get(WorkerRow, self.worker_id)
            if row is not None:
                row.heartbeat_at, row.stopped = queue.now(), stopped
                s.commit()

    async def _extend_lease(self, claimed: queue.Claimed, lost: asyncio.Event) -> None:
        while True:
            await asyncio.sleep(self.lease_s / 3)
            with self.session_factory() as s:
                ok = queue.heartbeat(s, claimed.job_id, self.worker_id, self.lease_s)
            self._beat()
            if not ok:
                lost.set()
                return

    async def _run_batch(self, claimed: queue.Claimed) -> None:
        handler = self.handlers.get(claimed.kind)
        with self.session_factory() as s:
            if handler is None:
                queue.fail_attempt(
                    s, claimed, self.worker_id, f"no handler for kind {claimed.kind!r}"
                )
                return
        lost = asyncio.Event()
        beat = asyncio.create_task(self._extend_lease(claimed, lost))
        ctx = BatchContext(claimed, lost)
        work = asyncio.create_task(handler.process(ctx))
        stop_wait = asyncio.create_task(self.stop.wait())
        try:
            await asyncio.wait({work, stop_wait}, return_when=asyncio.FIRST_COMPLETED)
            if not work.done():  # shutdown requested mid-batch: allow a grace period to finish
                await asyncio.wait({work}, timeout=self.grace_s)
            if not work.done():
                work.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await work
                with self.session_factory() as s:
                    queue.release(s, claimed.job_id, self.worker_id)
                log.info("released batch %s on shutdown", claimed.batch_idx)
                return
            results = work.result()
        except Exception as exc:
            with self.session_factory() as s:
                outcome = queue.fail_attempt(
                    s, claimed, self.worker_id, f"{type(exc).__name__}: {exc}"
                )
            log.warning(
                "batch %s attempt %s failed: %s (%s)",
                claimed.batch_idx,
                claimed.attempts,
                exc,
                outcome,
            )
            return
        finally:
            stop_wait.cancel()
            beat.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await beat
        with self.session_factory() as s:
            if not queue.commit_results(s, claimed, self.worker_id, results, ctx.hooks):
                log.warning("lease lost for batch %s; results discarded", claimed.batch_idx)

    async def run(self) -> None:
        self._register()
        log.info("worker %s started", self.worker_id)
        try:
            while not self.stop.is_set():
                self._beat()
                with self.session_factory() as s:
                    if self.guard is not None:
                        self.guard.check(s)
                    queue.settle_runs(s)
                    claimed = queue.claim_next(s, self.worker_id, self.lease_s)
                if claimed is None:
                    with contextlib.suppress(TimeoutError):
                        await asyncio.wait_for(self.stop.wait(), self.poll_s)
                    continue
                await self._run_batch(claimed)
        finally:
            self._beat(stopped=True)
            log.info("worker %s stopped", self.worker_id)


def install_signal_handlers(worker: Worker) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, worker.stop.set)
