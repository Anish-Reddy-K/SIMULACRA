from sqlalchemy.orm import Mapped, mapped_column

from simulacra.persistence.db import Base


class Setting(Base):
    """Key-value application settings. First table; proves the migration path."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[str]
