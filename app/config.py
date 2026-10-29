from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GG_", env_file=".env", extra="ignore")

    app_name: str = "Memora"  # product name shown in the UI and portfolio assets
    photos_dir: Path = Path("~/Pictures")
    db_path: Path = Path("data/gallery.db")
    model_id: str = "google/embeddinggemma-2"
    embed_dim: int = 256  # Matryoshka: 768 | 512 | 256 | 128
    top_k: int = 24

    @property
    def photos_root(self) -> Path:
        return self.photos_dir.expanduser().resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
