"""Famille couverture : loi Beta exacte, escomptage, plafond."""

import pytest
from scipy.stats import beta as beta_dist

from deciban.services import coverage


def test_aucun_controle_declenche_ne_prouve_rien() -> None:
    assert coverage.score(0, 0)["score"] == 0.0


def test_une_couverture_complete_pese_en_faveur_de_la_personne() -> None:
    assert coverage.score(10, 10)["score"] > 0


def test_des_controles_manques_pesent_a_charge() -> None:
    assert coverage.score(3, 10)["score"] < 0


def test_la_preuve_grandit_avec_le_volume() -> None:
    assert coverage.score(10, 10)["score"] > coverage.score(2, 2)["score"]


def test_le_plafond_de_famille_est_respecte() -> None:
    result = coverage.score(0, 40)
    assert result["score"] >= -coverage.FAMILY_CAP
    assert result["capped"] is True


def test_l_esperance_suit_l_estimateur_de_laplace() -> None:
    for answered, fired in ((11, 11), (4, 11), (1, 2)):
        missed = fired - answered
        expected = (answered + 1) / (answered + missed + 2)
        assert coverage.score(answered, fired)["mean"] == pytest.approx(expected, abs=1e-3)


def test_l_intervalle_est_le_quantile_exact_de_la_beta() -> None:
    """Et non plus une approximation normale d'une loi asymetrique."""
    answered, fired = 1, 2
    missed = fired - answered
    result = coverage.score(answered, fired)
    assert result["low"] == pytest.approx(
        float(beta_dist.ppf(0.05, answered + 1, missed + 1)), abs=1e-3
    )
    assert result["high"] == pytest.approx(
        float(beta_dist.ppf(0.95, answered + 1, missed + 1)), abs=1e-3
    )


def test_l_intervalle_reste_dans_les_bornes_sans_ecretage() -> None:
    """L'approximation normale sortait de [0, 1] sur petits echantillons."""
    for answered, fired in ((1, 1), (0, 1), (2, 2), (0, 2), (11, 11)):
        r = coverage.score(answered, fired)
        assert 0.0 <= r["low"] <= r["mean"] <= r["high"] <= 1.0


def test_l_intervalle_est_asymetrique_quand_la_loi_l_est() -> None:
    r = coverage.score(8, 8)
    below = r["mean"] - r["low"]
    above = r["high"] - r["mean"]
    assert below > above, "une Beta tres asymetrique doit produire un intervalle asymetrique"
