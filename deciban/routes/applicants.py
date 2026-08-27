"""Inscriptions a l'equipe."""

from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import func, select

from deciban.core.database import DbSession
from deciban.models.entities import Applicant
from deciban.schemas.payloads import ApplicantIn

router = APIRouter(tags=["applicants"])


@router.post("/applicants", status_code=status.HTTP_201_CREATED)
def create(payload: ApplicantIn, request: Request, db: DbSession) -> dict[str, Any]:
    exists = db.scalar(select(Applicant).where(Applicant.email == str(payload.email)))
    if exists:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Cette adresse est deja inscrite. Tu es dans la liste.",
        )

    applicant = Applicant(
        name=payload.name,
        email=str(payload.email),
        promethee_handle=payload.promethee_handle,
        github_handle=payload.github_handle,
        roles=payload.roles,
        availability=payload.availability,
        motivation=payload.motivation,
        source=payload.source,
        ip=request.client.host if request.client else None,
    )
    db.add(applicant)
    db.commit()
    db.refresh(applicant)

    position = db.scalar(
        select(func.count()).select_from(Applicant).where(Applicant.id <= applicant.id)
    )
    return {"message": "Candidature enregistree.", "position": position}


@router.get("/applicants/count")
def count(db: DbSession) -> dict[str, int]:
    return {"count": db.scalar(select(func.count()).select_from(Applicant)) or 0}
