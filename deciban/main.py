"""Point d'entree de l'API Deciban."""

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from deciban.core.config import get_settings
from deciban.core.database import Base, engine
from deciban.models import entities  # noqa: F401  (enregistre les tables)
from deciban.routes import applicants, sessions, system


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Deciban",
        description=(
            "Moteur de preuve d'humanite fonde sur l'accumulation de rapports "
            "de vraisemblance, exprimes en decibans."
        ),
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    app.include_router(applicants.router, prefix="/api")
    app.include_router(sessions.router, prefix="/api")
    app.include_router(system.router, prefix="/api")

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, Any]:
        return {"name": "Deciban", "docs": "/docs"}

    return app


app = create_app()

# En developpement les tables sont creees au demarrage ; en production
# c'est Alembic qui fait foi.
Base.metadata.create_all(bind=engine)
