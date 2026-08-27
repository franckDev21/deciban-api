"""Inscriptions a l'equipe."""

from fastapi.testclient import TestClient

VALID = {
    "name": "Franck Heaven",
    "email": "franck@example.cm",
    "roles": ["design", "backend"],
    "availability": "5-10h",
}


def test_une_candidature_valide_est_enregistree(client: TestClient) -> None:
    r = client.post("/api/applicants", json=VALID)
    assert r.status_code == 201
    assert r.json()["position"] == 1


def test_une_adresse_deja_inscrite_est_refusee(client: TestClient) -> None:
    assert client.post("/api/applicants", json=VALID).status_code == 201
    assert client.post("/api/applicants", json=VALID).status_code == 422
    assert client.get("/api/applicants/count").json()["count"] == 1


def test_le_piege_a_robots_rejette_la_requete(client: TestClient) -> None:
    payload = {**VALID, "website": "http://spam.io"}
    assert client.post("/api/applicants", json=payload).status_code == 422
    assert client.get("/api/applicants/count").json()["count"] == 0


def test_au_moins_un_domaine_est_obligatoire(client: TestClient) -> None:
    assert client.post("/api/applicants", json={**VALID, "roles": []}).status_code == 422


def test_un_domaine_inconnu_est_refuse(client: TestClient) -> None:
    assert client.post("/api/applicants", json={**VALID, "roles": ["pilotage"]}).status_code == 422


def test_un_identifiant_github_invalide_est_refuse(client: TestClient) -> None:
    payload = {**VALID, "github_handle": "pas valide !"}
    assert client.post("/api/applicants", json=payload).status_code == 422


def test_le_compteur_public_reflete_les_inscriptions(client: TestClient) -> None:
    assert client.get("/api/applicants/count").json()["count"] == 0
    client.post("/api/applicants", json=VALID)
    assert client.get("/api/applicants/count").json()["count"] == 1
