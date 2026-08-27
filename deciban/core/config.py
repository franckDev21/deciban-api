"""Configuration de l'application, lue depuis l'environnement."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./deciban.sqlite"
    frontend_urls: str = "http://localhost:3000"

    vapid_subject: str = "mailto:contact@deciban.local"
    vapid_public_key: str = ""
    vapid_private_key: str = ""

    @property
    def cors_origins(self) -> list[str]:
        return [u.strip() for u in self.frontend_urls.split(",") if u.strip()]

    @property
    def push_configured(self) -> bool:
        return bool(self.vapid_public_key and self.vapid_private_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
