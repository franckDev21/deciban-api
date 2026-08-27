"""Cognition, rythme et provenance."""

from datetime import timedelta
from types import SimpleNamespace

from deciban.models.entities import utcnow
from deciban.services import cognition, provenance, rhythm


def _session(start_offset_h: float, duration_min: float) -> SimpleNamespace:
    start = utcnow() - timedelta(hours=start_offset_h)
    return SimpleNamespace(starts_at=start, ends_at=start + timedelta(minutes=duration_min))


def _probe(**features: object) -> SimpleNamespace:
    return SimpleNamespace(features=features, score=None, status="answered")


def test_une_difficulte_constante_rend_la_correlation_indefinie() -> None:
    trials = [{"difficulty": 1, "latency_ms": x} for x in (700, 800, 900)]
    signal = cognition.score(trials, None, None, None)["signals"][0]
    assert signal["observed"] == "donnees insuffisantes"
    assert signal["db"] == 0.0


def test_une_latence_qui_suit_la_difficulte_est_creditee() -> None:
    trials = [
        {"difficulty": d, "latency_ms": lat} for d, lat in ((1, 180), (2, 260), (3, 300), (4, 410))
    ]
    signal = cognition.score(trials, None, None, None)["signals"][0]
    assert signal["db"] == 5.0


def test_une_latence_indifferente_au_contenu_est_a_charge() -> None:
    trials = [
        {"difficulty": d, "latency_ms": lat} for d, lat in ((1, 300), (2, 298), (3, 301), (4, 299))
    ]
    assert cognition.score(trials, None, None, None)["signals"][0]["db"] < 0


def test_une_lecture_surhumaine_est_a_charge() -> None:
    signals = cognition.score([], None, reading_ms=200, reading_words=60)["signals"]
    assert next(s for s in signals if s["key"] == "reading")["db"] < 0


def test_le_rebond_apres_exces_est_une_preuve_positive() -> None:
    """Une machine n'a pas de dette de sommeil a rembourser."""
    sessions = [
        _session(72, 19 * 60),
        _session(48, 19 * 60),
        _session(24, 19 * 60),
        _session(2, 60),  # effondrement
    ]
    signal = next(s for s in rhythm.score(sessions)["signals"] if s["key"] == "rebound")
    assert signal["db"] == 6.0


def test_des_journees_identiques_sont_a_charge() -> None:
    sessions = [_session(h, 120) for h in (96, 72, 48, 24)]
    signal = next(s for s in rhythm.score(sessions)["signals"] if s["key"] == "day_variance")
    assert signal["db"] < 0


def test_du_texte_colle_partout_est_a_charge() -> None:
    probes = [_probe(pasted=True) for _ in range(4)]
    signal = next(s for s in provenance.score(probes)["signals"] if s["key"] == "typed_ratio")
    assert signal["db"] == -5.0


def test_du_texte_frappe_est_credite() -> None:
    probes = [_probe(pasted=False) for _ in range(4)]
    signal = next(s for s in provenance.score(probes)["signals"] if s["key"] == "typed_ratio")
    assert signal["db"] == 4.0


def test_l_absence_de_revision_sur_plusieurs_controles_est_a_charge() -> None:
    probes = [_probe(pasted=False, backspaces=0) for _ in range(4)]
    signal = next(s for s in provenance.score(probes)["signals"] if s["key"] == "revisions")
    assert signal["db"] == -4.0


def test_les_plafonds_de_famille_sont_respectes() -> None:
    for module, block in (
        (cognition, cognition.score([], None, None, None)),
        (provenance, provenance.score([])),
        (rhythm, rhythm.score([])),
    ):
        assert abs(block["score"]) <= module.FAMILY_CAP
