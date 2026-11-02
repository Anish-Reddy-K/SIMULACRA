from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from simulacra import __version__
from simulacra.api import health
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
        try:
            yield
        finally:
            app.state.engine.dispose()

    app = FastAPI(title="Simulacra", version=__version__, lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)
    app.include_router(health.router, prefix="/api/v1")

    # Registered last so it never shadows API routes. Absent until `npm run build` has run.
    if settings.web_dir.is_dir():
        app.mount("/", StaticFiles(directory=settings.web_dir, html=True), name="web")
    return app
