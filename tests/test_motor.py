"""Famille motrice : separation, plafonds, absence de penalite."""

import pytest

from deciban.services import motor
from tests import factories


def test_une_trace_humaine_produit_une_preuve_positive() -> None:
    assert motor.score(factories.human(), reaction_ms=760)["score"] > 0


def test_une_trace_de_script_produit_une_preuve_accablante() -> None:
    result = motor.score(factories.script(), pasted=True, reaction_ms=45)
    assert result["score"] < 0
    assert result["raw"] < -15, "le brut doit s'effondrer avant plafonnement"


def test_les_deux_traces_sont_nettement_separees() -> None:
    human = motor.score(factories.human(), reaction_ms=760)["score"]
    script = motor.score(factories.script(), pasted=True, reaction_ms=45)["score"]
    assert human - script >= 10, "au moins dix decibans, soit dix contre un"


def test_le_plafond_de_famille_ecrete_dans_les_deux_sens() -> None:
    result = motor.score(factories.script(), pasted=True, reaction_ms=45)
    assert result["capped"] is True
    assert result["score"] == pytest.approx(-motor.FAMILY_CAP, abs=0.01)
    assert result["raw"] < result["score"]


def test_un_signal_sans_donnees_contribue_zero_jamais_une_penalite() -> None:
    maigre = [
        {"t": 0, "type": "move", "x": 1, "y": 1},
        {"t": 16, "type": "move", "x": 2, "y": 2},
        {"t": 32, "type": "move", "x": 3, "y": 3},
    ]
    for signal in motor.score(maigre)["signals"]:
        assert signal["db"] >= 0, f"{signal['key']} penalise une absence de donnees"


def test_le_collage_est_compte_a_charge() -> None:
    typed = motor.score(factories.human(), pasted=False, reaction_ms=760)["raw"]
    pasted = motor.score(factories.human(), pasted=True, reaction_ms=760)["raw"]
    assert pasted < typed


def test_une_reaction_surhumaine_est_suspecte() -> None:
    signals = motor.score(factories.human(), reaction_ms=40)["signals"]
    reaction = next(s for s in signals if s["key"] == "reaction")
    assert reaction["db"] < 0


def test_la_saisie_tactile_est_non_applicable_sans_penalite() -> None:
    result = motor.score(factories.script(), pasted=True, reaction_ms=40, input_mode="touch")
    assert result["score"] == 0.0
    assert result["not_applicable"] is True


def test_le_tremblement_isole_bien_la_bande_8_12_hz() -> None:
    dans_la_bande = motor.tremor_ratio(
        [e for e in factories.human(tremor_hz=9.7) if e["type"] == "move"]
    )
    hors_bande = motor.tremor_ratio(
        [e for e in factories.human(tremor_hz=2.0) if e["type"] == "move"]
    )
    lisse = motor.tremor_ratio([e for e in factories.script() if e["type"] == "move"])

    assert dans_la_bande > 0.09
    assert hors_bande < 0.09, "une agitation lente ne doit pas passer pour un tremblement"
    assert lisse < 0.09
    assert dans_la_bande > hors_bande * 2


def test_le_tremblement_ne_depend_pas_de_la_cadence_d_echantillonnage() -> None:
    """Le rapport de puissance doit rester comparable d'une machine a l'autre."""
    lent = motor.tremor_ratio([e for e in factories.human(tremor_hz=9.7) if e["type"] == "move"])
    # Meme signal, echantillonne deux fois plus vite.
    rapide_events = []
    for e in factories.human(tremor_hz=9.7):
        if e["type"] == "move":
            rapide_events.append({**e, "t": e["t"] * 0.5})
    rapide = motor.tremor_ratio(rapide_events)

    assert lent is not None and rapide is not None
