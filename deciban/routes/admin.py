"""Espace d'administration : consulter les candidatures recues.

Un seul compte, celui du responsable. Les adresses e-mail des personnes
inscrites ne doivent jamais transiter sans authentification : c'est la
raison d'etre de ce module.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select

from deciban.core.config import get_settings
from deciban.core.database import DbSession
from deciban.core.security import issue_token, read_token, verify_password
from deciban.models.entities import Applicant

router = APIRouter(prefix="/admin", tags=["admin"])


class LoginIn(BaseModel):
    email: EmailStr
    password: str


def require_admin(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    """Refuse tout ce qui ne porte pas un jeton valide."""
    settings = get_settings()

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentification requise.")

    payload = read_token(authorization.removeprefix("Bearer "), settings.secret_key)
    if payload is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expiree ou invalide.")

    return str(payload["sub"])


AdminUser = Annotated[str, Depends(require_admin)]


@router.post("/login")
def login(payload: LoginIn) -> dict[str, Any]:
    settings = get_settings()

    if not settings.admin_configured:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Aucun compte d'administration n'est configure sur ce serveur.",
        )

    email_ok = payload.email.lower() == settings.admin_email.lower()
    # Le mot de passe est verifie meme si l'adresse est fausse : sans cela,
    # le temps de reponse revelerait quelles adresses existent.
    password_ok = verify_password(payload.password, settings.admin_password_hash)

    if not (email_ok and password_ok):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Identifiants incorrects.")

    return {"token": issue_token(settings.admin_email, settings.secret_key)}


@router.get("/applicants")
def list_applicants(_: AdminUser, db: DbSession) -> dict[str, Any]:
    rows = db.scalars(select(Applicant).order_by(Applicant.id.desc())).all()

    by_role: dict[str, int] = {}
    for a in rows:
        for r in a.roles or []:
            by_role[r] = by_role.get(r, 0) + 1

    return {
        "total": len(rows),
        "by_role": dict(sorted(by_role.items(), key=lambda kv: -kv[1])),
        "applicants": [
            {
                "id": a.id,
                "name": a.name,
                "email": a.email,
                "promethee_handle": a.promethee_handle,
                "github_handle": a.github_handle,
                "roles": a.roles,
                "availability": a.availability,
                "motivation": a.motivation,
                "status": a.status,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in rows
        ],
    }


@router.get("/summary")
def summary(_: AdminUser, db: DbSession) -> dict[str, Any]:
    return {
        "applicants": db.scalar(select(func.count()).select_from(Applicant)) or 0,
    }
