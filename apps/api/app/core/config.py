from functools import lru_cache
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Raíz del repositorio: las rutas relativas se anclan acá, no al directorio desde el que se arranca el proceso.
REPO_ROOT = Path(__file__).resolve().parents[4]

PLATFORM_VERSION = "0.1.0"
API_VERSION = "v1"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HUB_", env_file=".env", extra="ignore")

    env: str = "development"
    database_url: str = ""
    plugins_dir: Path = Path("plugins")
    data_dir: Path = Path("data")
    allow_untrusted_plugins: bool = False
    cors_origins: str = "http://localhost:5173"

    @field_validator("plugins_dir", "data_dir")
    @classmethod
    def _anchor(cls, v: Path) -> Path:
        return v if v.is_absolute() else (REPO_ROOT / v).resolve()

    @model_validator(mode="after")
    def _default_db(self) -> "Settings":
        if not self.database_url:
            self.database_url = f"sqlite:///{self.data_dir / 'hub.sqlite3'}"
        elif self.database_url.startswith("sqlite:///./"):
            self.database_url = f"sqlite:///{(REPO_ROOT / self.database_url[len('sqlite:///./'):]).resolve()}"
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
