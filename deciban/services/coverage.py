"""Famille « couverture attestee ».

On tire k controles a des instants uniformes dans la fenetre declaree.
Le taux de reussite estime c, la fraction des heures reellement assistee.

Amelioration par rapport au portage PHP : l'intervalle de credibilite est
desormais calcule par la fonction quantile EXACTE de la loi Beta, et non
par une approximation normale d'une loi fortement asymetrique.
"""

from math import log
from typing import Any

from scipy.stats import beta as beta_dist

FAMILY_CAP = 15.0

#: Presence normale d'une personne qui declare ce qu'elle travaille.
C_HUMAN = 0.95
#: Compte qui reclame vingt heures par jour et ne peut en couvrir que six
#: sur dix, un tiers de ses heures tombant pendant son sommeil.
C_FARMER = 0.60

#: En deca de ce nombre de controles, la preuve est escomptee : deux
#: reussites ne peuvent pas valoir autant que dix.
FULL_CONFIDENCE_AT = 8


def score(answered: int, fired: int, /) -> dict[str, Any]:
    """Preuve apportee par la couverture.

    :param answered: controles auxquels la personne a repondu
    :param fired: controles DECLENCHES, reponses et manques confondus.
                  Ce n'est pas le nombre de manques : les confondre
                  inverse completement le resultat.
    """
    if fired <= 0:
        return {
            "score": 0.0,
            "raw": 0.0,
            "capped": False,
            "mean": 0.0,
            "low": 0.0,
            "high": 0.0,
            "answered": 0,
            "fired": 0,
        }

    missed = fired - answered

    # Posterieure de Jeffreys-Laplace : Beta(a+1, m+1) apres un a priori uniforme.
    a = answered + 1
    b = missed + 1
    mean = a / (a + b)

    # Quantiles exacts, et non plus moyenne +/- 1,645 ecart-type.
    low = float(beta_dist.ppf(0.05, a, b))
    high = float(beta_dist.ppf(0.95, a, b))

    # Rapport de vraisemblance binomial : le coefficient du binome se
    # simplifie entre les deux hypotheses, il n'apparait donc pas ici.
    ll_human = answered * log(C_HUMAN) + missed * log(1 - C_HUMAN)
    ll_farmer = answered * log(C_FARMER) + missed * log(1 - C_FARMER)
    raw = 10.0 * (ll_human - ll_farmer) / log(10)

    # Ecretage assume, non bayesien : la vraisemblance croit deja en n.
    raw *= min(1.0, fired / FULL_CONFIDENCE_AT)

    capped = max(-FAMILY_CAP, min(FAMILY_CAP, raw))

    return {
        "score": round(capped, 2),
        "raw": round(raw, 2),
        "capped": abs(raw) > FAMILY_CAP,
        "mean": round(mean, 3),
        "low": round(low, 3),
        "high": round(high, 3),
        "answered": answered,
        "fired": fired,
    }
