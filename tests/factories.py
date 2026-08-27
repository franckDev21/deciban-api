"""Fabriques de traces de controle, humaines ou mecaniques."""

import math
import random
from typing import Any

#: Cadence typique des evenements de pointeur d'un navigateur.
SAMPLE_MS = 1000 / 60


def human(seed: int = 7, tremor_hz: float = 9.6, amplitude: float = 1.4) -> list[dict[str, Any]]:
    """Geste vivant : tremblement dans la bande, corrections, chevauchements."""
    rng = random.Random(seed)
    events: list[dict[str, Any]] = []
    t = 0.0
    x = y = 300.0

    for i in range(140):
        t += SAMPLE_MS
        x += 4.0
        y += 1.6
        phase = 2 * math.pi * tremor_hz * (t / 1000)
        x += amplitude * math.sin(phase) + rng.gauss(0, 0.2)
        y += amplitude * math.cos(phase * 1.07) + rng.gauss(0, 0.2)
        if i in (48, 82, 112):
            x -= rng.uniform(9, 16)
            y += rng.uniform(7, 13)
        events.append({"t": round(t, 1), "type": "move", "x": round(x, 1), "y": round(y, 1)})

    previous_down = t
    for ch in "bonjourjesuisbienla":
        down = previous_down + rng.uniform(70, 120)
        # Maintien plus long que l'intervalle : la touche suivante part avant
        # le relachement, ce qui produit le chevauchement propre a l'humain.
        dwell = rng.uniform(90, 160)
        code = "Key" + ch.upper()
        events.append({"t": round(down, 1), "type": "down", "code": code})
        events.append({"t": round(down + dwell, 1), "type": "up", "code": code})
        previous_down = down

    return events


def script() -> list[dict[str, Any]]:
    """Trajectoire rectiligne, maintien constant, aucun chevauchement."""
    events: list[dict[str, Any]] = []
    t = 0.0
    x = y = 300.0

    for _ in range(140):
        t += SAMPLE_MS
        x += 5.0
        y += 2.0
        events.append({"t": round(t, 1), "type": "move", "x": x, "y": y})

    for ch in "bonjourjesuisbienla":
        down = t + 80.0
        code = "Key" + ch.upper()
        events.append({"t": round(down, 1), "type": "down", "code": code})
        events.append({"t": round(down + 40.0, 1), "type": "up", "code": code})
        t = down + 40.0

    return events
