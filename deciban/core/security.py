"""Authentification de l'espace d'administration.

Un seul compte, celui du responsable du projet. Pas de table
utilisateurs : l'identifiant et l'empreinte du mot de passe vivent dans
l'environnement, comme le reste des secrets.

Aucune dependance ajoutee : pbkdf2 et hmac sont dans la bibliotheque
standard, et suffisent pour un compte unique.
"""

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

#: Cout de derivation. Volontairement eleve : la verification n'arrive
#: qu'une fois par connexion, mais chaque essai d'un attaquant la subit.
ITERATIONS = 240_000
#: Duree de vie d'une session d'administration.
TOKEN_TTL = 12 * 3600


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def hash_password(password: str, salt: bytes | None = None) -> str:
    """Retourne « pbkdf2$iterations$sel$empreinte »."""
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2${ITERATIONS}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    """Comparaison a temps constant : une egalite naive fuiterait le mot de passe."""
    try:
        scheme, iterations, salt, digest = stored.split("$")
        if scheme != "pbkdf2":
            return False
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), _unb64(salt), int(iterations))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(candidate, _unb64(digest))


def issue_token(subject: str, secret: str, ttl: int = TOKEN_TTL) -> str:
    """Jeton signe, sans etat cote serveur : « charge.signature »."""
    payload = {"sub": subject, "exp": int(time.time()) + ttl}
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    signature = hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest()
    return f"{body}.{_b64(signature)}"


def read_token(token: str, secret: str) -> dict[str, Any] | None:
    """Retourne la charge si la signature tient et que le jeton n'a pas expire."""
    try:
        body, signature = token.split(".")
        expected = hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(_unb64(signature), expected):
            return None
        payload: dict[str, Any] = json.loads(_unb64(body))
    except (ValueError, TypeError, json.JSONDecodeError):
        return None

    if payload.get("exp", 0) < time.time():
        return None
    return payload
