from pathlib import Path

from sqlalchemy import inspect

from simulacra.persistence import migrate
from simulacra.persistence.db import make_engine


def test_upgrade_and_downgrade_round_trip(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 't.db'}"
    migrate.upgrade(url)
    engine = make_engine(url)
    assert "settings" in inspect(engine).get_table_names()

    migrate.downgrade(url)
    assert "settings" not in inspect(engine).get_table_names()
    migrate.upgrade(url)  # re-applies cleanly
    assert "settings" in inspect(engine).get_table_names()
    engine.dispose()


def test_models_match_migrations(tmp_path: Path) -> None:
    """Fails if someone edits a model without adding a migration."""
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from simulacra.persistence.db import Base

    url = f"sqlite:///{tmp_path / 't.db'}"
    migrate.upgrade(url)
    engine = make_engine(url)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    engine.dispose()
    assert diff == []
