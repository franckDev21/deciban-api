"""Famille « signature motrice ».

Chaque signal renvoie une quantite de preuve en decibans :

    preuve = 10 * log10( P(observation | humain) / P(observation | machine) )

Les valeurs restent une calibration initiale plausible, pas une mesure.

Amelioration par rapport au portage PHP : le tremblement est mesure par un
VRAI passe-bande a 8-12 Hz, sur un signal reechantillonne a pas constant,
et exprime comme un RAPPORT de puissance. Il devient donc comparable d'une
machine a l'autre, ce que la difference seconde ne permettait pas.
"""

from collections.abc import Sequence
from math import atan2, hypot, pi
from statistics import fmean, pstdev
from typing import Any

import numpy as np
from scipy import signal as sp_signal

FAMILY_CAP = 8.0

#: Bande du tremblement physiologique humain.
TREMOR_BAND = (8.0, 12.0)
#: Bande de reference : on rapporte la puissance du tremblement a celle-ci.
REFERENCE_BAND = (2.0, 20.0)
#: Frequence de reechantillonnage, au-dessus du double de 20 Hz.
RESAMPLE_HZ = 100.0

Event = dict[str, Any]


def _insufficient(key: str, label: str) -> dict[str, Any]:
    """Un signal sans donnees contribue zero, jamais une penalite."""
    return {"key": key, "label": label, "observed": "donnees insuffisantes", "db": 0.0}


def tremor_ratio(moves: Sequence[Event]) -> float | None:
    """Part de la puissance spectrale tombant dans la bande 8-12 Hz.

    Les evenements du navigateur arrivent a pas irregulier : on interpole
    donc sur une grille reguliere avant toute analyse frequentielle.
    """
    if len(moves) < 48:
        return None

    t = np.asarray([float(m["t"]) for m in moves], dtype=float) / 1000.0
    x = np.asarray([float(m["x"]) for m in moves], dtype=float)
    y = np.asarray([float(m["y"]) for m in moves], dtype=float)

    span = t[-1] - t[0]
    if span < 0.75:
        return None

    grid = np.arange(t[0], t[-1], 1.0 / RESAMPLE_HZ)
    if grid.size < 64:
        return None

    xi = np.interp(grid, t, x)
    yi = np.interp(grid, t, y)

    # On retire la trajectoire lente pour ne garder que la micro-agitation.
    detrended = np.column_stack(
        [sp_signal.detrend(xi, type="linear"), sp_signal.detrend(yi, type="linear")]
    )

    nperseg = min(128, detrended.shape[0])
    total_band = 0.0
    total_ref = 0.0

    for axis in range(2):
        freqs, psd = sp_signal.welch(
            detrended[:, axis], fs=RESAMPLE_HZ, nperseg=nperseg, detrend="constant"
        )
        band = (freqs >= TREMOR_BAND[0]) & (freqs <= TREMOR_BAND[1])
        ref = (freqs >= REFERENCE_BAND[0]) & (freqs <= REFERENCE_BAND[1])
        total_band += float(np.trapezoid(psd[band], freqs[band])) if band.any() else 0.0
        total_ref += float(np.trapezoid(psd[ref], freqs[ref])) if ref.any() else 0.0

    if total_ref <= 0:
        return None

    return total_band / total_ref


def _tremor(moves: Sequence[Event]) -> dict[str, Any]:
    ratio = tremor_ratio(moves)
    if ratio is None:
        return _insufficient("tremor", "Micro-tremblement")

    # Seuils mesures sur traces synthetiques : le plancher des traces
    # porteuses d'un tremblement en bande est 0,081, le plafond de celles
    # qui n'en portent pas est 0,083. La frontiere passe donc juste au-
    # dessus. Ces valeurs restent a re-estimer sur de vraies personnes.
    if ratio >= 0.14:
        db = 5.0
    elif ratio >= 0.09:
        db = 3.0
    elif ratio >= 0.05:
        db = 0.0
    else:
        db = -6.0

    return {
        "key": "tremor",
        "label": "Micro-tremblement",
        "observed": f"{ratio * 100:.1f} % de la puissance en bande 8-12 Hz",
        "db": db,
    }


def _submovements(moves: Sequence[Event]) -> dict[str, Any]:
    """Loi de Fitts : un geste humain est balistique puis corrige."""
    if len(moves) < 12:
        return _insufficient("submovements", "Corrections de cap")

    corrections = 0
    for i in range(2, len(moves)):
        a1 = atan2(moves[i - 1]["y"] - moves[i - 2]["y"], moves[i - 1]["x"] - moves[i - 2]["x"])
        a2 = atan2(moves[i]["y"] - moves[i - 1]["y"], moves[i]["x"] - moves[i - 1]["x"])
        d = abs(a2 - a1)
        if d > pi:
            d = 2 * pi - d
        if d > 0.9:
            corrections += 1

    if corrections >= 8:
        db = 3.0
    elif corrections >= 3:
        db = 2.0
    elif corrections >= 1:
        db = 0.0
    else:
        db = -4.0

    return {
        "key": "submovements",
        "label": "Corrections de cap",
        "observed": f"{corrections} changements de direction",
        "db": db,
    }


def _sinuosity(moves: Sequence[Event]) -> dict[str, Any]:
    if len(moves) < 12:
        return _insufficient("sinuosity", "Sinuosite du trace")

    path = sum(
        hypot(moves[i]["x"] - moves[i - 1]["x"], moves[i]["y"] - moves[i - 1]["y"])
        for i in range(1, len(moves))
    )
    direct = hypot(moves[-1]["x"] - moves[0]["x"], moves[-1]["y"] - moves[0]["y"])
    if direct < 8:
        return _insufficient("sinuosity", "Sinuosite du trace")

    ratio = path / direct
    if ratio >= 1.15:
        db = 2.0
    elif ratio >= 1.04:
        db = 1.0
    else:
        db = -3.0

    return {
        "key": "sinuosity",
        "label": "Sinuosite du trace",
        "observed": f"rapport {ratio:.3f}",
        "db": db,
    }


def _rollover(events: Sequence[Event]) -> dict[str, Any]:
    """Un humain rapide appuie sur la touche suivante avant de relacher."""
    downs = [e for e in events if e.get("type") == "down"]
    if len(downs) < 6:
        return _insufficient("rollover", "Chevauchement de touches")

    ordered = sorted(events, key=lambda e: e["t"])
    open_keys: set = set()
    presses = 0
    overlaps = 0

    for e in ordered:
        kind = e.get("type")
        if kind == "down":
            if open_keys:
                overlaps += 1
            open_keys.add(e.get("code", "?"))
            presses += 1
        elif kind == "up":
            open_keys.discard(e.get("code", "?"))

    ratio = overlaps / (presses - 1) if presses > 1 else 0.0
    if ratio >= 0.05:
        db = 3.0
    elif ratio > 0:
        db = 1.0
    else:
        db = -3.0

    return {
        "key": "rollover",
        "label": "Chevauchement de touches",
        "observed": f"{ratio * 100:.1f} % des frappes",
        "db": db,
    }


def _dwell(events: Sequence[Event]) -> dict[str, Any]:
    downs = [e for e in events if e.get("type") == "down"]
    ups = [e for e in events if e.get("type") == "up"]

    dwells: list[float] = []
    for d in downs:
        for u in ups:
            if u.get("code") == d.get("code") and u["t"] > d["t"]:
                dwells.append(u["t"] - d["t"])
                break

    if len(dwells) < 6:
        return _insufficient("dwell", "Duree de maintien")

    mean = fmean(dwells)
    if mean <= 0:
        return _insufficient("dwell", "Duree de maintien")

    cv = pstdev(dwells) / mean
    if cv >= 0.25:
        db = 2.0
    elif cv >= 0.12:
        db = 0.0
    else:
        db = -5.0

    return {
        "key": "dwell",
        "label": "Duree de maintien",
        "observed": f"coefficient de variation {cv:.2f}",
        "db": db,
    }


def _reaction(ms: float | None) -> dict[str, Any]:
    if ms is None:
        return _insufficient("reaction", "Temps de reaction")

    if ms < 120:
        db = -4.0  # plus rapide qu'une perception humaine
    elif ms <= 4000:
        db = 2.0
    else:
        db = 0.0

    return {
        "key": "reaction",
        "label": "Temps de reaction",
        "observed": f"{round(ms)} ms",
        "db": db,
    }


def score(
    events: Sequence[Event],
    pasted: bool = False,
    reaction_ms: float | None = None,
    input_mode: str = "pointer",
) -> dict[str, Any]:
    # Sur ecran tactile, la famille n'a rien de comparable a mesurer : elle
    # devient non applicable et contribue zero, jamais une penalite. Meme
    # regle que pour un materiel absent.
    if input_mode == "touch":
        return {
            "score": 0.0,
            "raw": 0.0,
            "capped": False,
            "not_applicable": True,
            "signals": [
                {
                    "key": "touch",
                    "label": "Famille non applicable",
                    "observed": "saisie tactile, aucun signal moteur comparable",
                    "db": 0.0,
                }
            ],
        }

    moves = [e for e in events if e.get("type") == "move"]

    signals = [
        _tremor(moves),
        _submovements(moves),
        _sinuosity(moves),
        _rollover(events),
        _dwell(events),
        _reaction(reaction_ms),
    ]

    if pasted:
        signals.append(
            {
                "key": "paste",
                "label": "Contenu colle",
                "observed": "le texte a ete colle, pas frappe",
                "db": -4.0,
            }
        )

    raw = sum(s["db"] for s in signals)
    capped = max(-FAMILY_CAP, min(FAMILY_CAP, raw))

    return {
        "score": round(capped, 2),
        "raw": round(raw, 2),
        "capped": abs(raw) > FAMILY_CAP,
        "signals": signals,
    }
