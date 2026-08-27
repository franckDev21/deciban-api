"""Famille « provenance du travail ».

Mesure la paternite plutot que la presence : distingue « j'etais la » de
« c'est bien moi qui ai produit ca ».
"""

from collections.abc import Sequence
from typing import Any

FAMILY_CAP = 10.0


def _insufficient(key: str, label: str) -> dict[str, Any]:
    return {"key": key, "label": label, "observed": "donnees insuffisantes", "db": 0.0}


def _feature(probe: Any, key: str, default: Any = None) -> Any:
    return (probe.features or {}).get(key, default)


def _typed_ratio(answered: Sequence[Any]) -> dict[str, Any]:
    if not answered:
        return _insufficient("typed_ratio", "Ratio frappe / colle")

    pasted = sum(1 for p in answered if _feature(p, "pasted", False))
    ratio = 1 - (pasted / len(answered))

    if ratio >= 0.9:
        db = 4.0
    elif ratio >= 0.6:
        db = 1.0
    elif ratio >= 0.3:
        db = -2.0
    else:
        db = -5.0

    return {
        "key": "typed_ratio",
        "label": "Ratio frappe / colle",
        "observed": f"{round(ratio * 100)} % frappe au clavier",
        "db": db,
    }


def _revisions(answered: Sequence[Any]) -> dict[str, Any]:
    if len(answered) < 3:
        return _insufficient("revisions", "Revisions d'edition")

    total = sum(int(_feature(p, "backspaces", 0) or 0) for p in answered)
    with_revision = sum(1 for p in answered if int(_feature(p, "backspaces", 0) or 0) > 0)
    ratio = with_revision / len(answered)

    if ratio >= 0.3:
        db = 3.0
    elif ratio > 0:
        db = 1.0
    else:
        db = -4.0

    return {
        "key": "revisions",
        "label": "Revisions d'edition",
        "observed": f"{total} correction(s) sur {len(answered)} controle(s)",
        "db": db,
    }


def _live_response(answered: Sequence[Any]) -> dict[str, Any]:
    if len(answered) < 2:
        return _insufficient("live_response", "Reponse sous contrainte")

    fast = 0
    for p in answered:
        r = _feature(p, "reaction_ms")
        if r is not None and 150 <= float(r) <= 30000:
            fast += 1

    ratio = fast / len(answered)
    if ratio >= 0.7:
        db = 5.0
    elif ratio >= 0.4:
        db = 2.0
    else:
        db = 0.0

    return {
        "key": "live_response",
        "label": "Reponse sous contrainte",
        "observed": f"{fast} reponse(s) dans un delai humain",
        "db": db,
    }


def score(answered: Sequence[Any]) -> dict[str, Any]:
    signals = [_typed_ratio(answered), _revisions(answered), _live_response(answered)]
    raw = sum(s["db"] for s in signals)
    capped = max(-FAMILY_CAP, min(FAMILY_CAP, raw))
    return {
        "score": round(capped, 2),
        "raw": round(raw, 2),
        "capped": abs(raw) > FAMILY_CAP,
        "signals": signals,
    }
