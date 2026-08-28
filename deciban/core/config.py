"""Configuration de l'application, lue depuis l'environnement."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./deciban.sqlite"
    frontend_urls: str = "http://localhost:3000"

    #: Origines acceptees en plus de la liste ci-dessus, decrites par une
    #: expression reguliere. Sans elle, une preproduction Vercel — dont
    #: l'adresse change a chaque deploiement — et un poste de developpement
    #: sont refuses par le navigateur, et l'API parait morte alors qu'elle
    #: repond parfaitement en direct.
    frontend_url_regex: str = (
        r"^https://deciban-web(-[a-z0-9-]+)?\.vercel\.app$"
        r"|^http://(localhost|127\.0\.0\.1)(:\d+)?$"
    )

    vapid_subject: str = "mailto:contact@deciban.local"
    vapid_public_key: str = ""
    vapid_private_key: str = ""

    #: Compte unique de l'espace d'administration.
    admin_email: str = ""
    #: Empreinte pbkdf2, jamais le mot de passe en clair.
    admin_password_hash: str = ""
    #: Signe les jetons de session. Doit etre change en production.
    secret_key: str = "changez-moi-en-production"

    @property
    def cors_origins(self) -> list[str]:
        return [u.strip() for u in self.frontend_urls.split(",") if u.strip()]

    @property
    def cors_origin_regex(self) -> str | None:
        """None plutot que la chaine vide : Starlette teste la presence."""
        return self.frontend_url_regex or None

    @property
    def admin_configured(self) -> bool:
        return bool(self.admin_email and self.admin_password_hash)

    @property
    def push_configured(self) -> bool:
        return bool(self.vapid_public_key and self.vapid_private_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
