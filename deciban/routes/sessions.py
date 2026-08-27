"""Cycle de vie d'une session : ouverture, controles, attestation."""

import secrets
import string
import uuid
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from deciban.core.config import get_settings
from deciban.core.database import DbSession
from deciban.models.entities import Probe, PushSubscription, WorkSession, utcnow
from deciban.schemas.payloads import ProbeAnswerIn, SessionIn, SubscriptionIn
from deciban.services import motor, report

router = APIRouter(tags=["sessions"])

_ALPHABET = string.ascii_lowercase + string.digits


def _slug(length: int = 8) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


def _sweep(db: Session, session: WorkSession) -> None:
    """Declenche les controles dus et expire ceux restes sans reponse.

    Appele a chaque consultation, ce qui garantit un etat coherent meme
    sans tache planifiee.
    """
    now = utcnow()
    changed = False

    for probe in session.probes:
        if probe.status == "pending" and probe.fire_at <= now:
            probe.status = "fired"
            probe.notified_at = now
            changed = True

    for probe in session.probes:
        if probe.status == "fired" and probe.answered_at is None:
            reference = probe.notified_at or probe.fire_at
            if (now - reference).total_seconds() > Probe.WINDOW:
                probe.status = "missed"
                changed = True

    if changed:
        db.commit()


def _get_session(db: Session, token: str) -> WorkSession:
    session = db.scalar(select(WorkSession).where(WorkSession.token == token))
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session introuvable.")
    return session


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
def open_session(payload: SessionIn, request: Request, db: DbSession) -> dict[str, Any]:
    minutes = payload.minutes
    count = payload.probes or max(3, min(10, minutes // 45))

    starts_at = utcnow()
    session = WorkSession(
        token=str(uuid.uuid4()),
        slug=_slug(),
        handle=payload.handle,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=minutes),
        probe_count=count,
        ip=request.client.host if request.client else None,
    )
    db.add(session)
    db.flush()

    # Tirage uniforme dans la fenetre, avec une marge aux deux bouts pour
    # qu'aucun controle ne tombe hors de la periode utile.
    span = minutes * 60
    margin = min(60, int(span * 0.03))
    offsets = sorted(secrets.randbelow(max(1, span - 2 * margin)) + margin for _ in range(count))

    for offset in offsets:
        db.add(
            Probe(
                work_session_id=session.id,
                token=str(uuid.uuid4()),
                fire_at=starts_at + timedelta(seconds=offset),
            )
        )

    db.commit()
    db.refresh(session)

    return {
        "token": session.token,
        "slug": session.slug,
        "ends_at": session.ends_at.isoformat(),
        "probe_count": count,
        "vapid_public_key": get_settings().vapid_public_key,
    }


@router.get("/sessions/{token}")
def show_session(token: str, db: DbSession) -> dict[str, Any]:
    session = _get_session(db, token)
    _sweep(db, session)

    due: Probe | None = next(
        (
            p
            for p in sorted(session.probes, key=lambda p: p.fire_at)
            if p.status == "fired" and p.answered_at is None
        ),
        None,
    )

    payload: dict[str, Any] = {"session": report.build(db, session), "due": None}
    if due is not None:
        reference = due.notified_at or due.fire_at
        remaining = Probe.WINDOW - int((utcnow() - reference).total_seconds())
        payload["due"] = {"token": due.token, "expires_in": max(0, remaining)}
    return payload


@router.post("/probes/{probe_token}")
def answer_probe(probe_token: str, payload: ProbeAnswerIn, db: DbSession) -> dict[str, Any]:
    probe = db.scalar(select(Probe).where(Probe.token == probe_token))
    if probe is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Controle introuvable.")

    if probe.status == "answered":
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce controle a deja recu une reponse.")
    if probe.status != "fired":
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce controle n'est pas ouvert.")

    reference = probe.notified_at or probe.fire_at
    if (utcnow() - reference).total_seconds() > Probe.WINDOW:
        probe.status = "missed"
        db.commit()
        raise HTTPException(status.HTTP_410_GONE, "Fenetre de reponse expiree.")

    result = motor.score(
        payload.as_events(),
        pasted=payload.pasted,
        reaction_ms=payload.reaction_ms,
        input_mode=payload.input_mode,
    )

    extra = {
        k: v
        for k, v in {
            "pasted": payload.pasted,
            "reaction_ms": payload.reaction_ms,
            "difficulty": payload.difficulty,
            "typed_chars": payload.typed_chars,
            "expected_chars": payload.expected_chars,
            "adjacent_errors": payload.adjacent_errors,
            "backspaces": payload.backspaces,
            "reading_ms": payload.reading_ms,
            "reading_words": payload.reading_words,
        }.items()
        if v is not None
    }

    probe.status = "answered"
    probe.answered_at = utcnow()
    probe.score = result["score"]
    probe.features = {**result, **extra}
    db.commit()
    db.refresh(probe)

    return {"probe": result, "session": report.build(db, probe.session)}


@router.get("/attestations/{slug}")
def attestation(slug: str, db: DbSession) -> dict[str, Any]:
    session = db.scalar(select(WorkSession).where(WorkSession.slug == slug))
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cette attestation n'existe pas.")
    _sweep(db, session)
    return report.build(db, session)


@router.post("/sessions/{token}/subscribe", status_code=status.HTTP_201_CREATED)
def subscribe(token: str, payload: SubscriptionIn, db: DbSession) -> dict[str, str]:
    session = _get_session(db, token)

    existing = db.scalar(
        select(PushSubscription).where(PushSubscription.endpoint == payload.endpoint)
    )
    if existing:
        existing.work_session_id = session.id
        existing.p256dh = payload.keys.p256dh
        existing.auth = payload.keys.auth
    else:
        db.add(
            PushSubscription(
                work_session_id=session.id,
                endpoint=payload.endpoint,
                p256dh=payload.keys.p256dh,
                auth=payload.keys.auth,
            )
        )
    db.commit()
    return {"message": "Abonnement enregistre."}
