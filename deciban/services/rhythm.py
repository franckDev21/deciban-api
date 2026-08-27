"""Famille « rythme de vie ».

Se calcule sur l'historique des sessions d'une meme personne, pas sur un
controle isole. Le signal central n'est pas le sommeil mais la DETTE de
sommeil : un humain peut tenir trois jours sans dormir, personne ne tient
trois semaines. Ce qui suit un exces, l'effondrement, est une preuve
d'humanite plus forte qu'un rythme regulier.
"""

from collections import defaultdict
from collections.abc import Sequence
from statistics import fmean, pstdev
from typing import Any

FAMILY_CAP = 12.0

#: Fenetre glissante sur laquelle la dette doit se resorber.
WINDOW_DAYS = 21


def _insufficient(key: str, label: str) -> dict[str, Any]:
    return {"key": key, "label": label, "observed": "donnees insuffisantes", "db": 0.0}


def _gaps_hours(sessions: Sequence[Any]) -> list[float]:
    gaps = []
    previous_end = None
    for s in sessions:
        if previous_end is not None:
            gaps.append((s.starts_at - previous_end).total_seconds() / 3600)
        previous_end = s.ends_at
    return gaps


def _sleep_debt(sessions: Sequence[Any]) -> dict[str, Any]:
    if len(sessions) < 2:
        return _insufficient("sleep_debt", "Dette de sommeil")

    gaps = _gaps_hours(sessions)
    if not gaps:
        return _insufficient("sleep_debt", "Dette de sommeil")

    longest = max(gaps)
    span_days = max(1.0, (sessions[-1].ends_at - sessions[0].starts_at).total_seconds() / 86400)
    restful = sum(1 for g in gaps if g >= 4)

    if longest >= 4 and restful >= span_days * 0.5:
        db = 5.0
    elif longest >= 4:
        db = 3.0
    elif span_days >= 3:
        db = -9.0
    else:
        db = 0.0

    # Sur un historique court, la preuve est fortement escomptee.
    confidence = min(1.0, span_days / 7)

    return {
        "key": "sleep_debt",
        "label": "Dette de sommeil",
        "observed": f"plus longue pause {longest:.1f} h sur {span_days:.1f} jour(s)",
        "db": round(db * confidence, 1),
    }


def _minutes_by_day(sessions: Sequence[Any]) -> list[float]:
    by_day: dict[str, float] = defaultdict(float)
    for s in sessions:
        key = s.starts_at.date().isoformat()
        by_day[key] += (s.ends_at - s.starts_at).total_seconds() / 60
    return [by_day[k] for k in sorted(by_day)]


def _rebound(sessions: Sequence[Any]) -> dict[str, Any]:
    """Un exces suivi d'un effondrement est une preuve POSITIVE."""
    if len(sessions) < 4:
        return _insufficient("rebound", "Rebond apres exces")

    values = _minutes_by_day(sessions)
    if len(values) < 3:
        return _insufficient("rebound", "Rebond apres exces")

    peak = max(values)
    if peak < 240:
        return _insufficient("rebound", "Rebond apres exces")

    after = values[values.index(peak) + 1 :]
    dropped = bool(after) and min(after) <= peak * 0.5

    return {
        "key": "rebound",
        "label": "Rebond apres exces",
        "observed": (
            f"pic de {peak / 60:.1f} h suivi d'un effondrement"
            if dropped
            else f"pic de {peak / 60:.1f} h sans repos ensuite"
        ),
        "db": 6.0 if dropped else 0.0,
    }


def _break_distribution(sessions: Sequence[Any]) -> dict[str, Any]:
    """Les pauses humaines suivent une queue lourde, jamais une horloge."""
    if len(sessions) < 4:
        return _insufficient("breaks", "Distribution des pauses")

    gaps = [g * 60 for g in _gaps_hours(sessions)]
    if len(gaps) < 3:
        return _insufficient("breaks", "Distribution des pauses")

    mean = fmean(gaps)
    if mean <= 0:
        return _insufficient("breaks", "Distribution des pauses")

    cv = pstdev(gaps) / mean
    if cv >= 0.6:
        db = 3.0
    elif cv >= 0.25:
        db = 1.0
    else:
        db = -4.0

    return {
        "key": "breaks",
        "label": "Distribution des pauses",
        "observed": f"coefficient de variation {cv:.2f}",
        "db": db,
    }


def _day_variance(sessions: Sequence[Any]) -> dict[str, Any]:
    """Les bons et les mauvais jours existent."""
    values = _minutes_by_day(sessions)
    if len(values) < 3:
        return _insufficient("day_variance", "Variance inter-jours")

    mean = fmean(values)
    if mean <= 0:
        return _insufficient("day_variance", "Variance inter-jours")

    cv = pstdev(values) / mean
    if cv >= 0.3:
        db = 2.0
    elif cv >= 0.1:
        db = 0.0
    else:
        db = -4.0

    return {
        "key": "day_variance",
        "label": "Variance inter-jours",
        "observed": f"coefficient de variation {cv:.2f}",
        "db": db,
    }


def score(sessions: Sequence[Any]) -> dict[str, Any]:
    ordered = sorted(sessions, key=lambda s: s.starts_at)
    signals = [
        _sleep_debt(ordered),
        _rebound(ordered),
        _break_distribution(ordered),
        _day_variance(ordered),
    ]
    raw = sum(s["db"] for s in signals)
    capped = max(-FAMILY_CAP, min(FAMILY_CAP, raw))
    return {
        "score": round(capped, 2),
        "raw": round(raw, 2),
        "capped": abs(raw) > FAMILY_CAP,
        "signals": signals,
    }
