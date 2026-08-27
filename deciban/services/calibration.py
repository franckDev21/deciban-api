"""Re-estimation des poids sur donnees etiquetees.

Les poids livres sont une calibration initiale PLAUSIBLE, pas une mesure.
Ce module fabrique la mesure des qu'il existe des etiquettes, et refuse de
deviner tant qu'il n'y en a pas.
"""

from collections.abc import Sequence
from math import log10
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from deciban.models.entities import ProbeLabel

#: En deca, toute estimation serait du bruit presente comme un resultat.
MIN_LABELS_PER_CLASS = 30


def _positive_rate(labels: Sequence[ProbeLabel], key: str) -> float:
    if not labels:
        return 0.0
    positive = 0
    for label in labels:
        for s in (label.probe.features or {}).get("signals", []):
            if s.get("key") == key:
                if s.get("db", 0) > 0:
                    positive += 1
                break
    return positive / len(labels)


def _estimate(human: Sequence[ProbeLabel], machine: Sequence[ProbeLabel]) -> list[dict[str, Any]]:
    keys: dict[str, str] = {}
    for label in list(human) + list(machine):
        for s in (label.probe.features or {}).get("signals", []):
            keys[s["key"]] = s["label"]

    out = []
    for key, label in keys.items():
        p_h = _positive_rate(human, key)
        p_m = _positive_rate(machine, key)
        # Correction de Laplace : evite un rapport infini sur un signal qui
        # n'apparait jamais dans l'une des deux classes.
        p_h = (p_h * len(human) + 1) / (len(human) + 2)
        p_m = (p_m * len(machine) + 1) / (len(machine) + 2)
        out.append(
            {
                "key": key,
                "label": label,
                "p_human": round(p_h, 3),
                "p_machine": round(p_m, 3),
                "estimated_db": round(10 * log10(p_h / p_m), 2),
            }
        )
    return out


def _separation(human: Sequence[ProbeLabel], machine: Sequence[ProbeLabel]) -> dict[str, Any]:
    """Taux de faux positifs a taux de detection fixe.

    C'est la seule metrique qui compte : une exactitude globale ne veut rien
    dire sur une population desequilibree.
    """
    h = np.sort(np.asarray([p.probe.score or 0.0 for p in human], dtype=float))
    m = np.asarray([p.probe.score or 0.0 for p in machine], dtype=float)

    # Seuil qui laisse passer 95 % des humains.
    threshold = float(np.quantile(h, 0.05))
    fpr = float((m >= threshold).mean()) if m.size else None

    return {
        "threshold_db": round(threshold, 2),
        "true_positive_rate": 0.95,
        "false_positive_rate": round(fpr, 4) if fpr is not None else None,
        "note": "Taux de faux positifs mesure au seuil qui accepte 95 % des humains.",
    }


def report(db: Session) -> dict[str, Any]:
    labels = list(db.scalars(select(ProbeLabel).options(selectinload(ProbeLabel.probe))))
    human = [x for x in labels if x.is_human]
    machine = [x for x in labels if not x.is_human]

    ready = len(human) >= MIN_LABELS_PER_CLASS and len(machine) >= MIN_LABELS_PER_CLASS

    return {
        "labels": {
            "human": len(human),
            "machine": len(machine),
            "required_per_class": MIN_LABELS_PER_CLASS,
        },
        "ready": ready,
        "status": (
            "Donnees suffisantes pour une premiere re-estimation."
            if ready
            else "Donnees insuffisantes. Les poids en service restent une calibration "
            "initiale non validee, et aucun chiffre de performance ne peut etre revendique."
        ),
        "signals": _estimate(human, machine) if ready else [],
        "separation": _separation(human, machine) if ready else None,
    }
