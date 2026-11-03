import argparse
import asyncio
import logging
import subprocess
import sys
import threading
import time

import uvicorn
from sqlalchemy.orm import sessionmaker

from simulacra.api.app import create_app
from simulacra.config import get_settings
from simulacra.jobs.handlers import default_registry
from simulacra.jobs.resources import ResourceGuard
from simulacra.jobs.worker import Worker, install_signal_handlers
from simulacra.persistence import migrate
from simulacra.persistence.db import make_engine

WORKER_RESTART_DELAY_S = 2.0


def _supervise_worker(stop: threading.Event, keep_awake: bool = False) -> None:
    """Keep one worker process alive next to the API; restart it if it dies."""
    proc: subprocess.Popen[bytes] | None = None
    while not stop.is_set():
        if proc is None or proc.poll() is not None:
            if proc is not None:
                logging.getLogger("simulacra").warning(
                    "worker exited (%s); restarting", proc.returncode
                )
                stop.wait(WORKER_RESTART_DELAY_S)
                if stop.is_set():
                    break
            proc = subprocess.Popen([sys.executable, "-m", "simulacra.cli", "worker"])
        stop.wait(1.0)
    if proc is not None and proc.poll() is None:
        proc.terminate()  # SIGTERM: the worker finishes or releases its batch, then exits
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="simulacra")
    sub = parser.add_subparsers(dest="command", required=True)
    up = sub.add_parser("up", help="start the API, web UI and background worker on localhost")
    up.add_argument("--no-worker", action="store_true", help="do not start the worker process")
    up.add_argument(
        "--keep-awake",
        action="store_true",
        help="macOS: prevent idle sleep only while the worker runs (the lid still sleeps the Mac)",
    )
    sub.add_parser("worker", help="run the background worker on its own")
    sub.add_parser("migrate", help="apply database migrations")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    if args.command == "migrate":
        migrate.upgrade(settings.database_url)
    elif args.command == "worker":
        migrate.upgrade(settings.database_url)
        engine = make_engine(settings.database_url)
        sessions = sessionmaker(engine, expire_on_commit=False)
        worker = Worker(
            sessions,
            default_registry(settings.enable_mock_backend, sessions),
            lease_s=settings.worker_lease_s,
            guard=ResourceGuard(settings.data_dir),
        )

        async def main_async() -> None:
            install_signal_handlers(worker)
            await worker.run()

        asyncio.run(main_async())
    elif args.command == "up":
        stop = threading.Event()
        thread = None
        if not args.no_worker:
            thread = threading.Thread(
                target=_supervise_worker, args=(stop, args.keep_awake), daemon=True
            )
            thread.start()
        try:
            uvicorn.run(create_app(settings), host=settings.host, port=settings.port)
        finally:
            stop.set()
            if thread is not None:
                thread.join(timeout=40)
            time.sleep(0)


if __name__ == "__main__":
    main()
