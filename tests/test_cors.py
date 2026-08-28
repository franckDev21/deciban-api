"""Origines acceptees par le navigateur.

Regression : la production n'autorisait qu'une seule adresse. Toute
preproduction Vercel — dont l'adresse change a chaque deploiement — et tout
poste de developpement recevaient un refus du navigateur, ce qui donnait
l'impression d'une API morte alors qu'elle repondait parfaitement en direct.
"""

import pytest
from fastapi.testclient import TestClient


def preflight(client: TestClient, origin: str) -> str | None:
    response = client.options(
        "/api/sessions",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    return response.headers.get("access-control-allow-origin")


@pytest.mark.parametrize(
    "origin",
    [
        "https://deciban-web.vercel.app",
        "https://deciban-web-git-main-franck.vercel.app",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
)
def test_origines_acceptees(client: TestClient, origin: str) -> None:
    assert preflight(client, origin) == origin


@pytest.mark.parametrize(
    "origin",
    [
        "https://autre-projet.vercel.app",
        "https://deciban-web.vercel.app.attaquant.tld",
        "http://deciban-web.vercel.app",
    ],
)
def test_origines_refusees(client: TestClient, origin: str) -> None:
    assert preflight(client, origin) is None
