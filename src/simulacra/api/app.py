import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import sessionmaker
from starlette.middleware.trustedhost import TrustedHostMiddleware

from simulacra import __version__
from simulacra.api import health, lab
from simulacra.benchmarks import repository as repo
from simulacra.config import Settings, get_settings
from simulacra.persistence import migrate
from simulacra.persistence.db import make_engine

# Reject any other Host header: blocks DNS-rebinding attacks against the local API.
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        migrate.upgrade(settings.database_url)
        app.state.engine = make_engine(settings.database_url)
        app.state.sessions = sessionmaker(app.state.engine, expire_on_commit=False)
        app.state.settings = settings
        app.state.benchmark_tasks = {}
        with app.state.sessions() as session:
            repo.mark_interrupted(session)  # runs orphaned by a previous crash or restart
        try:
            yield
        finally:
            for task in app.state.benchmark_tasks.values():
                task.cancel()
            await asyncio.gather(*app.state.benchmark_tasks.values(), return_exceptions=True)
            app.state.engine.dispose()

    app = FastAPI(title="Simulacra", version=__version__, lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)

    @app.middleware("http")
    async def reject_cross_origin_writes(request: Request, call_next):  # type: ignore[no-untyped-def]
        """CSRF defense: a web page on another origin must not be able to POST to this API.

        Browsers always send Origin on cross-origin writes. Same-origin and non-browser
        clients (curl, tests) either match or send none.
        """
        origin = request.headers.get("origin")
        if request.method not in ("GET", "HEAD", "OPTIONS") and origin is not None:
            parsed = urlparse(origin)
            allowed_ports = {settings.port, settings.dev_web_port}
            if parsed.hostname not in ALLOWED_HOSTS or parsed.port not in allowed_ports:
                return JSONResponse({"detail": "Cross-origin request rejected"}, status_code=403)
        return await call_next(request)

    app.include_router(health.router, prefix="/api/v1")
    app.include_router(lab.router, prefix="/api/v1")

    # Registered last so it never shadows API routes. Absent until `npm run build` has run.
    if settings.web_dir.is_dir():
        app.mount("/", StaticFiles(directory=settings.web_dir, html=True), name="web")
    return app
