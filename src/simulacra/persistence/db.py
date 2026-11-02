from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import ConnectionPoolEntry


class Base(DeclarativeBase):
    pass


def _set_sqlite_pragmas(dbapi_conn: Any, _record: ConnectionPoolEntry) -> None:
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA busy_timeout=5000")
    cur.close()


def make_engine(url: str) -> Engine:
    """Create a SQLite engine with WAL and the safety pragmas from ADR-0003."""
    engine = create_engine(url)
    event.listen(engine, "connect", _set_sqlite_pragmas)
    return engine
