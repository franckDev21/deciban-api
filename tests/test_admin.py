"""Espace d'administration : ce qui protege les adresses des inscrits."""

import pytest
from fastapi.testclient import TestClient

from deciban.core.config import get_settings
from deciban.core.security import hash_password, issue_token, verify_password

EMAIL = "chef@deciban-admin.com"
PASSWORD = "un-mot-de-passe-solide"


@pytest.fixture
def admin_configured():
    s = get_settings()
    avant = (s.admin_email, s.admin_password_hash, s.secret_key)
    s.admin_email = EMAIL
    s.admin_password_hash = hash_password(PASSWORD)
    s.secret_key = "cle-de-test"
    yield s
    s.admin_email, s.admin_password_hash, s.secret_key = avant


def _token(client: TestClient) -> str:
    r = client.post("/api/admin/login", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 200
    return r.json()["token"]


def test_les_bons_identifiants_ouvrent_une_session(client, admin_configured) -> None:
    assert _token(client)


def test_un_mauvais_mot_de_passe_est_refuse(client, admin_configured) -> None:
    r = client.post("/api/admin/login", json={"email": EMAIL, "password": "faux"})
    assert r.status_code == 401


def test_une_adresse_inconnue_est_refusee(client, admin_configured) -> None:
    r = client.post("/api/admin/login", json={"email": "autre@x.co", "password": PASSWORD})
    assert r.status_code == 401


def test_la_liste_est_inaccessible_sans_jeton(client, admin_configured) -> None:
    """Les adresses e-mail des inscrits ne doivent jamais fuiter."""
    assert client.get("/api/admin/applicants").status_code == 401


def test_un_jeton_bidon_est_refuse(client, admin_configured) -> None:
    r = client.get("/api/admin/applicants", headers={"Authorization": "Bearer nimporte.quoi"})
    assert r.status_code == 401


def test_un_jeton_signe_avec_une_autre_cle_est_refuse(client, admin_configured) -> None:
    faux = issue_token(EMAIL, "cle-de-l-attaquant")
    r = client.get("/api/admin/applicants", headers={"Authorization": f"Bearer {faux}"})
    assert r.status_code == 401


def test_un_jeton_expire_est_refuse(client, admin_configured) -> None:
    perime = issue_token(EMAIL, "cle-de-test", ttl=-10)
    r = client.get("/api/admin/applicants", headers={"Authorization": f"Bearer {perime}"})
    assert r.status_code == 401


def test_la_liste_montre_les_candidatures(client, admin_configured) -> None:
    client.post(
        "/api/applicants",
        json={
            "name": "Marie Dupont",
            "email": "marie@example.cm",
            "roles": ["design", "frontend"],
            "availability": "5-10h",
            "motivation": "Le design me parle.",
        },
    )
    r = client.get("/api/admin/applicants", headers={"Authorization": f"Bearer {_token(client)}"})
    assert r.status_code == 200

    corps = r.json()
    assert corps["total"] == 1
    assert corps["by_role"]["design"] == 1
    inscrit = corps["applicants"][0]
    assert inscrit["email"] == "marie@example.cm"
    assert inscrit["motivation"] == "Le design me parle."


def test_sans_compte_configure_la_connexion_est_indisponible(client) -> None:
    s = get_settings()
    avant = s.admin_email
    s.admin_email = ""
    try:
        r = client.post("/api/admin/login", json={"email": "a@b.co", "password": "x"})
        assert r.status_code == 503
    finally:
        s.admin_email = avant


def test_l_empreinte_ne_contient_jamais_le_mot_de_passe() -> None:
    h = hash_password("mon-secret-en-clair")
    assert "mon-secret-en-clair" not in h
    assert verify_password("mon-secret-en-clair", h)
    assert not verify_password("mon-secret-en-clai", h)
