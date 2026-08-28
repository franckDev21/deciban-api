"""Parcours complet d'une session, de l'ouverture a l'attestation."""

from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from deciban.models.entities import Probe, WorkSession, utcnow
from tests import factories


def _open(client: TestClient, minutes: int = 60, probes: int = 4) -> dict[str, Any]:
    r = client.post(
        "/api/sessions",
        json={"handle": "Franck Heaven", "minutes": minutes, "probes": probes},
    )
    assert r.status_code == 201
    return r.json()


def _arm_first_probe(db: Session, token: str) -> None:
    session = db.scalar(select(WorkSession).where(WorkSession.token == token))
    assert session is not None
    probe = sorted(session.probes, key=lambda p: p.fire_at)[0]
    probe.fire_at = utcnow() - timedelta(seconds=1)
    db.commit()


def test_ouvrir_une_session_tire_les_controles_demandes(client, db_session) -> None:
    body = _open(client, 60, 4)
    session = db_session.scalar(select(WorkSession).where(WorkSession.token == body["token"]))
    assert body["probe_count"] == 4
    assert len(session.probes) == 4


def test_la_reponse_d_ouverture_ne_divulgue_aucun_horaire(client) -> None:
    body = _open(client)
    assert "probes" not in body
    assert "fire_at" not in str(body)


def test_consulter_la_session_ne_divulgue_jamais_le_prochain_controle(client) -> None:
    body = _open(client)
    r = client.get(f"/api/sessions/{body['token']}")
    assert r.json()["session"]["probes"]["next"] == "inconnu, par conception"


def test_les_controles_sont_tires_a_des_instants_distincts(client, db_session) -> None:
    body = _open(client, 240, 8)
    session = db_session.scalar(select(WorkSession).where(WorkSession.token == body["token"]))
    instants = {p.fire_at for p in session.probes}
    assert len(instants) > 1, "un tirage identique partout n'est pas aleatoire"


def test_les_controles_tombent_dans_la_fenetre_declaree(client, db_session) -> None:
    body = _open(client, 120, 6)
    session = db_session.scalar(select(WorkSession).where(WorkSession.token == body["token"]))
    for probe in session.probes:
        assert session.starts_at <= probe.fire_at <= session.ends_at


def test_un_controle_du_devient_disponible_et_accepte_une_reponse(client, db_session) -> None:
    body = _open(client)
    _arm_first_probe(db_session, body["token"])

    due = client.get(f"/api/sessions/{body['token']}").json()["due"]
    assert due is not None

    r = client.post(
        f"/api/probes/{due['token']}",
        json={"events": factories.human(), "pasted": False, "reaction_ms": 760},
    )
    assert r.status_code == 200
    assert r.json()["session"]["probes"]["answered"] == 1


def test_un_controle_ne_peut_pas_recevoir_deux_reponses(client, db_session) -> None:
    body = _open(client)
    _arm_first_probe(db_session, body["token"])
    due = client.get(f"/api/sessions/{body['token']}").json()["due"]
    payload = {"events": factories.human(), "reaction_ms": 700}

    assert client.post(f"/api/probes/{due['token']}", json=payload).status_code == 200
    assert client.post(f"/api/probes/{due['token']}", json=payload).status_code == 409


def test_un_controle_expire_est_compte_comme_manque(client, db_session) -> None:
    body = _open(client)
    session = db_session.scalar(select(WorkSession).where(WorkSession.token == body["token"]))
    probe = sorted(session.probes, key=lambda p: p.fire_at)[0]
    stale = utcnow() - timedelta(seconds=Probe.WINDOW + 30)
    probe.status = "fired"
    probe.fire_at = stale
    probe.notified_at = stale
    db_session.commit()

    r = client.get(f"/api/sessions/{body['token']}")
    assert r.json()["session"]["probes"]["missed"] == 1

    assert (
        client.post(f"/api/probes/{probe.token}", json={"events": factories.human()}).status_code
        == 409
    )


def test_une_trace_de_script_pese_moins_qu_une_trace_humaine(client, db_session) -> None:
    def score_for(events, pasted, reaction):
        body = _open(client)
        _arm_first_probe(db_session, body["token"])
        due = client.get(f"/api/sessions/{body['token']}").json()["due"]
        return client.post(
            f"/api/probes/{due['token']}",
            json={"events": events, "pasted": pasted, "reaction_ms": reaction},
        ).json()["probe"]["score"]

    human = score_for(factories.human(), False, 760)
    script = score_for(factories.script(), True, 40)
    assert human > script


def test_l_attestation_publique_ne_contient_aucun_secret(client) -> None:
    body = _open(client)
    r = client.get(f"/api/attestations/{body['slug']}")
    assert r.status_code == 200
    assert body["token"] not in r.text, "le token de session fuite"
    assert "fire_at" not in r.text, "un horaire de controle fuite"


def test_une_attestation_inconnue_renvoie_une_absence(client) -> None:
    assert client.get("/api/attestations/inexistant").status_code == 404


def test_une_trace_vide_est_refusee(client, db_session) -> None:
    body = _open(client)
    _arm_first_probe(db_session, body["token"])
    due = client.get(f"/api/sessions/{body['token']}").json()["due"]
    assert client.post(f"/api/probes/{due['token']}", json={"events": []}).status_code == 422


def test_une_duree_hors_bornes_est_refusee(client) -> None:
    assert client.post("/api/sessions", json={"minutes": 5}).status_code == 422
    assert client.post("/api/sessions", json={"minutes": 5000}).status_code == 422


def test_le_rapport_expose_les_cinq_familles(client) -> None:
    body = _open(client)
    families = client.get(f"/api/sessions/{body['token']}").json()["session"]["families"]
    assert [f["key"] for f in families] == [
        "coverage",
        "rhythm",
        "provenance",
        "cognition",
        "motor",
    ]


def test_un_abonnement_push_est_enregistre(client) -> None:
    body = _open(client)
    r = client.post(
        f"/api/sessions/{body['token']}/subscribe",
        json={
            "endpoint": "https://push.example/abc",
            # Longueurs reelles d'un abonnement navigateur : 65 octets pour
            # la cle publique, 16 pour le secret, encodes en base64url.
            "keys": {"p256dh": "BM" + "a" * 84, "auth": "c" * 22},
        },
    )
    assert r.status_code == 201
