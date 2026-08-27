"""Etat du systeme et calibration, publies pour pouvoir etre contestes."""

from typing import Any

from fastapi import APIRouter
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from deciban.core.config import get_settings
from deciban.core.database import DbSession
from deciban.models.entities import Heartbeat, Probe, utcnow
from deciban.services import calibration

router = APIRouter(tags=["system"])

#: Au-dela de ce delai sans battement, le repartiteur est considere arrete.
STALE_AFTER_SECONDS = 120

DISPATCHER = "dispatcher"


def touch(db: Session, name: str = DISPATCHER) -> None:
    """Enregistre un signal de vie, visible depuis tout autre processus."""
    row = db.get(Heartbeat, name)
    if row is None:
        db.add(Heartbeat(name=name, beat_at=utcnow()))
    else:
        row.beat_at = utcnow()
    db.commit()


@router.get("/health")
def health(db: DbSession) -> dict[str, Any]:
    row = db.get(Heartbeat, DISPATCHER)
    at: str | None = row.beat_at.isoformat() if row else None
    alive = bool(row) and (utcnow() - row.beat_at).total_seconds() < STALE_AFTER_SECONDS

    pending = db.scalar(select(func.count()).select_from(Probe).where(Probe.status == "pending"))
    return {
        "api": True,
        "push_configured": get_settings().push_configured,
        "dispatcher": {"last_beat": at, "alive": alive},
        "pending_probes": pending or 0,
    }


@router.get("/vapid")
def vapid() -> dict[str, str]:
    return {"public_key": get_settings().vapid_public_key}


@router.get("/calibration")
def calibration_report(db: DbSession) -> dict[str, Any]:
    return calibration.report(db)
