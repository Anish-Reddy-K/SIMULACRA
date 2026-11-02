from functools import lru_cache
from pathlib import Path

from platformdirs import user_data_dir
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime configuration. Override any field with a SIMULACRA_* environment variable."""

    model_config = SettingsConfigDict(env_prefix="SIMULACRA_", extra="ignore")

    # The API is localhost-only by default (security requirement). Do not expose it
    # without adding authentication first.
    host: str = "127.0.0.1"
    port: int = 8765
    data_dir: Path = Field(default_factory=lambda: Path(user_data_dir("simulacra")))
    web_dir: Path = REPO_ROOT / "apps" / "web" / "out"

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.data_dir / 'simulacra.db'}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
