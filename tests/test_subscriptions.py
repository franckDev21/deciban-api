"""Validation des abonnements Web Push a l'entree de l'API.

Un abonnement mal forme accepte en base devient une bombe a retardement :
il ne se manifeste qu'au declenchement du controle suivant, dans le
repartiteur, loin de la requete qui l'a cree.
"""

import pytest
from pydantic import ValidationError

from deciban.schemas.payloads import SubscriptionIn

CLE_VALIDE = "BM" + "a" * 84
AUTH_VALIDE = "c" * 22


def _abonnement(**remplace: str) -> dict[str, object]:
    corps: dict[str, object] = {
        "endpoint": "https://fcm.googleapis.com/fcm/send/abc123",
        "keys": {"p256dh": CLE_VALIDE, "auth": AUTH_VALIDE},
    }
    corps.update(remplace)
    return corps


def test_un_abonnement_complet_est_accepte() -> None:
    assert SubscriptionIn(**_abonnement()).endpoint.startswith("https://")


def test_un_endpoint_vide_est_refuse() -> None:
    with pytest.raises(ValidationError):
        SubscriptionIn(**_abonnement(endpoint=""))


def test_un_endpoint_non_https_est_refuse() -> None:
    with pytest.raises(ValidationError):
        SubscriptionIn(**_abonnement(endpoint="http://push.example/en-clair"))


@pytest.mark.parametrize("longueur", [1, 49])
def test_une_cle_indecodable_est_refusee(longueur: int) -> None:
    """49 caracteres : 49 % 4 == 1, cas que base64 ne peut pas decoder.

    C'est exactement la valeur qui a fait tomber la production.
    """
    with pytest.raises(ValidationError):
        SubscriptionIn(**_abonnement(keys={"p256dh": "a" * longueur, "auth": AUTH_VALIDE}))


def test_une_cle_trop_courte_est_refusee() -> None:
    with pytest.raises(ValidationError):
        SubscriptionIn(**_abonnement(keys={"p256dh": "abcd", "auth": AUTH_VALIDE}))


def test_un_caractere_hors_alphabet_base64url_est_refuse() -> None:
    with pytest.raises(ValidationError):
        SubscriptionIn(**_abonnement(keys={"p256dh": "!" * 20, "auth": AUTH_VALIDE}))
