from alembic import context

from simulacra.persistence import models  # noqa: F401  (registers tables on Base.metadata)
from simulacra.persistence.db import Base, make_engine

config = context.config
target_metadata = Base.metadata


def run_migrations() -> None:
    engine = make_engine(config.get_main_option("sqlalchemy.url") or "")
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # SQLite cannot ALTER most things in place
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


run_migrations()
