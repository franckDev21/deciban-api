"""Point d'entree de l'API Deciban."""

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from deciban.core.config import get_settings
from deciban.core.schema import ensure_schema
from deciban.routes import admin, applicants, sessions, system


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
        allow_origin_regex=settings.cors_origin_regex,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    app.include_router(applicants.router, prefix="/api")
    app.include_router(sessions.router, prefix="/api")
    app.include_router(system.router, prefix="/api")
    app.include_router(admin.router, prefix="/api")

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, Any]:
        return {"name": "Deciban", "docs": "/docs"}

    return app


app = create_app()

ensure_schema()
