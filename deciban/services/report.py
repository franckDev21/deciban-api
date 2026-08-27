"""Assemble l'etat complet d'une session.

Regle centrale : les preuves de chaque famille s'additionnent, mais chaque
famille est plafonnee. Douze mesures d'un meme geste ne sont pas douze
preuves, c'est une observation vue sous douze angles.
"""

from collections.abc import Sequence
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from deciban.models.entities import Probe, WorkSession, utcnow
from deciban.services import cognition, coverage, motor, provenance, rhythm

#: Bornes de verdict, lues sur la preuve accumulee et jamais sur une
#: probabilite : sur preuve mince, celle-ci ne refleterait que la presomption.
VERDICTS = (
    (25.0, "verified", "Verifie"),
    (10.0, "credible", "Credible"),
    (-10.0, "undetermined", "Indetermine"),
    (-25.0, "watch", "A examiner"),
)


def _verdict(db: float) -> dict[str, str]:
    for threshold, key, label in VERDICTS:
        if db >= threshold:
            return {"key": key, "label": label}
    return {"key": "flagged", "label": "Signale"}


def _summarise(signals: Sequence[dict[str, Any]]) -> str:
    active = [s for s in signals if abs(s["db"]) > 0.01]
    if not active:
        return "donnees insuffisantes"
    return " · ".join(f"{s['label']} {'+' if s['db'] > 0 else ''}{s['db']}" for s in active[:3])


def _family(key: str, label: str, block: dict[str, Any], detail: str) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "db": block["score"],
        "raw": block["raw"],
        "capped": block["capped"],
        "detail": detail,
    }


def _motor_family(answered: Sequence[Probe]) -> dict[str, Any]:
    """Moyenne des controles, puis plafond de famille."""
    scores = [p.score for p in answered if p.score is not None]
    if not scores:
        return {"score": 0.0, "raw": 0.0, "capped": False, "detail": "donnees insuffisantes"}

    raw = sum(scores) / len(scores)
    kept = max(-motor.FAMILY_CAP, min(motor.FAMILY_CAP, raw))
    return {
        "score": round(kept, 2),
        "raw": round(raw, 2),
        "capped": abs(raw) > motor.FAMILY_CAP,
        "detail": f"moyenne sur {len(scores)} controle(s)",
    }


def _cognition_family(answered: Sequence[Probe]) -> dict[str, Any]:
    trials: list[dict[str, float]] = []
    typing = {"typed": 0, "expected": 0, "adjacent": 0, "backspaces": 0}
    reading_ms = None
    reading_words = None

    for p in answered:
        f = p.features or {}
        if f.get("difficulty") is not None and f.get("reaction_ms") is not None:
            trials.append(
                {"difficulty": float(f["difficulty"]), "latency_ms": float(f["reaction_ms"])}
            )
        for key, source in (
            ("typed", "typed_chars"),
            ("expected", "expected_chars"),
            ("adjacent", "adjacent_errors"),
            ("backspaces", "backspaces"),
        ):
            typing[key] += int(f.get(source) or 0)
        if reading_ms is None and f.get("reading_ms") and f.get("reading_words"):
            reading_ms = float(f["reading_ms"])
            reading_words = int(f["reading_words"])

    return cognition.score(
        trials, typing if typing["typed"] > 0 else None, reading_ms, reading_words
    )


def _person_history(db: Session, session: WorkSession) -> list[WorkSession]:
    """Sans identite stable, on retombe sur la seule session courante."""
    if not session.handle:
        return [session]

    since = utcnow() - timedelta(days=rhythm.WINDOW_DAYS)
    stmt = (
        select(WorkSession)
        .where(WorkSession.handle == session.handle, WorkSession.starts_at >= since)
        .order_by(WorkSession.starts_at)
    )
    return list(db.scalars(stmt))


def build(db: Session, session: WorkSession) -> dict[str, Any]:
    probes = sorted(session.probes, key=lambda p: p.fire_at)
    answered = [p for p in probes if p.status == "answered"]

    fired = sum(1 for p in probes if p.status in {"fired", "answered", "missed"})
    missed = sum(1 for p in probes if p.status == "missed")

    cov = coverage.score(len(answered), fired)
    mot = _motor_family(answered)
    cog = _cognition_family(answered)
    rhy = rhythm.score(_person_history(db, session))
    pro = provenance.score(answered)

    families = [
        _family(
            "coverage",
            "Couverture attestee",
            cov,
            (
                f"{len(answered)} sur {fired} · couverture {round(cov['mean'] * 100)} % "
                f"[{round(cov['low'] * 100)} – {round(cov['high'] * 100)} %]"
                if fired
                else "aucun controle declenche"
            ),
        ),
        _family("rhythm", "Rythme de vie", rhy, _summarise(rhy["signals"])),
        _family("provenance", "Provenance du travail", pro, _summarise(pro["signals"])),
        _family("cognition", "Cognition", cog, _summarise(cog["signals"])),
        _family("motor", "Signature motrice", mot, mot["detail"]),
    ]

    total = round(sum(f["db"] for f in families), 2)

    now = utcnow()
    horizon = min(now, session.ends_at)
    elapsed = max(0, int((horizon - session.starts_at).total_seconds()))

    return {
        "slug": session.slug,
        "handle": session.handle,
        "window": {
            "starts_at": session.starts_at.isoformat(),
            "ends_at": session.ends_at.isoformat(),
            "declared_minutes": int((session.ends_at - session.starts_at).total_seconds() // 60),
            "elapsed_seconds": elapsed,
            "over": now > session.ends_at,
        },
        "probes": {
            "total": session.probe_count,
            "fired": fired,
            "answered": len(answered),
            "missed": missed,
            # L'horaire n'est jamais transmis : c'est ce qui fait tenir le systeme.
            "next": "inconnu, par conception",
        },
        "families": families,
        "total_db": total,
        "verdict": _verdict(total),
    }
