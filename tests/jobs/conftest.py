import asyncio
import threading
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from sqlalchemy.orm import Session, sessionmaker

from simulacra.jobs.handlers import DemoHandler, Handler
from simulacra.jobs.worker import Worker
from simulacra.persistence import migrate
from simulacra.persistence.db import make_engine


@pytest.fixture
def db_url(tmp_path: Path) -> str:
    url = f"sqlite:///{tmp_path / 'jobs.db'}"
    migrate.upgrade(url)
    return url


@pytest.fixture
def sessions(db_url: str) -> Iterator[sessionmaker[Session]]:
    engine = make_engine(db_url)
    yield sessionmaker(engine, expire_on_commit=False)
    engine.dispose()


class ThreadWorker:
    """Runs a real Worker on its own event loop in a thread (stoppable, inspectable)."""

    def __init__(
        self,
        sessions: Callable[[], Session],
        handlers: dict[str, Handler] | None = None,
        **kw: float,
    ) -> None:
        self.worker = Worker(sessions, handlers or {"demo": DemoHandler()}, **kw)  # type: ignore[arg-type]
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.worker.run())

    def start(self) -> "ThreadWorker":
        self.thread.start()
        return self

    def stop(self) -> None:
        self.loop.call_soon_threadsafe(self.worker.stop.set)
        self.thread.join(timeout=15)


@pytest.fixture
def start_worker(sessions: sessionmaker[Session]) -> Iterator[Callable[..., ThreadWorker]]:
    started: list[ThreadWorker] = []

    def make(**kw: float) -> ThreadWorker:
        kw.setdefault("poll_s", 0.05)
        kw.setdefault("lease_s", 5.0)
        w = ThreadWorker(sessions, None, **kw).start()
        started.append(w)
        return w

    yield make
    for w in started:
        if w.thread.is_alive():
            w.stop()
