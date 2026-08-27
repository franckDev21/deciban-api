"""Famille « cognition ».

Mesure le rythme de la pensee plutot que celui du corps. Le signal central
est la correlation entre difficulte et temps de reponse : un humain met plus
longtemps sur une tache dure, une machine repond avec une latence
indifferente au contenu.
"""

from collections.abc import Sequence
from typing import Any

import numpy as np

FAMILY_CAP = 8.0


def _insufficient(key: str, label: str) -> dict[str, Any]:
    return {"key": key, "label": label, "observed": "donnees insuffisantes", "db": 0.0}


def _latency_difficulty(trials: Sequence[dict[str, float]]) -> dict[str, Any]:
    if len(trials) < 3:
        return _insufficient("latency_difficulty", "Latence liee a la difficulte")

    d = np.asarray([t["difficulty"] for t in trials], dtype=float)
    lat = np.asarray([t["latency_ms"] for t in trials], dtype=float)

    # Sans variance sur la difficulte, la correlation n'est pas definie.
    if d.std() == 0 or lat.std() == 0:
        return _insufficient("latency_difficulty", "Latence liee a la difficulte")

    r = float(np.corrcoef(d, lat)[0, 1])

    if r >= 0.45:
        db = 5.0
    elif r >= 0.20:
        db = 2.0
    elif r >= -0.10:
        db = -3.0
    else:
        db = -6.0

    return {
        "key": "latency_difficulty",
        "label": "Latence liee a la difficulte",
        "observed": f"correlation r = {r:.2f}",
        "db": db,
    }


def _reading(ms: float | None, words: int | None) -> dict[str, Any]:
    if ms is None or words is None or words < 4 or ms <= 0:
        return _insufficient("reading", "Vitesse de lecture")

    wpm = words / (ms / 60000)
    if 150 <= wpm <= 400:
        db = 2.0
    elif 400 < wpm <= 700:
        db = 0.0
    elif wpm > 700:
        db = -4.0  # personne ne lit si vite
    else:
        db = 0.0

    return {
        "key": "reading",
        "label": "Vitesse de lecture",
        "observed": f"{round(wpm)} mots par minute",
        "db": db,
    }


def _error_adjacency(typing: dict[str, int] | None) -> dict[str, Any]:
    if not typing or typing.get("typed", 0) < 10:
        return _insufficient("error_adjacency", "Adjacence des fautes")

    errors = max(0, typing.get("typed", 0) - typing.get("expected", 0))
    adjacent = typing.get("adjacent", 0)

    if errors == 0 and adjacent == 0:
        # Zero faute sur un echantillon court est normal chez un humain.
        if typing["typed"] > 60:
            return {
                "key": "error_adjacency",
                "label": "Adjacence des fautes",
                "observed": "aucune faute sur un long echantillon",
                "db": -3.0,
            }
        return _insufficient("error_adjacency", "Adjacence des fautes")

    ratio = adjacent / max(1, adjacent + errors)
    return {
        "key": "error_adjacency",
        "label": "Adjacence des fautes",
        "observed": f"{round(ratio * 100)} % sur touches voisines",
        "db": 3.0 if ratio >= 0.5 else 0.0,
    }


def _hesitation(typing: dict[str, int] | None) -> dict[str, Any]:
    if not typing or typing.get("typed", 0) < 10:
        return _insufficient("hesitation", "Retours arriere")

    back = typing.get("backspaces", 0)
    return {
        "key": "hesitation",
        "label": "Retours arriere",
        "observed": f"{back} correction(s)",
        "db": 2.0 if back > 0 else 0.0,
    }


def score(
    trials: Sequence[dict[str, float]],
    typing: dict[str, int] | None,
    reading_ms: float | None,
    reading_words: int | None,
) -> dict[str, Any]:
    signals: list[dict[str, Any]] = [
        _latency_difficulty(trials),
        _reading(reading_ms, reading_words),
        _error_adjacency(typing),
        _hesitation(typing),
    ]
    raw = sum(s["db"] for s in signals)
    capped = max(-FAMILY_CAP, min(FAMILY_CAP, raw))
    return {
        "score": round(capped, 2),
        "raw": round(raw, 2),
        "capped": abs(raw) > FAMILY_CAP,
        "signals": signals,
    }
