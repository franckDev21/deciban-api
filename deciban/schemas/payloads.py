"""Schemas d'entree et de sortie, valides par Pydantic."""

import base64
import binascii
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

ROLES = {
    "design",
    "frontend",
    "backend",
    "data",
    "securite",
    "test",
    "redaction",
    "autre",
}
AVAILABILITY = {"moins-2h", "2-5h", "5-10h", "plus-10h"}

GITHUB_RE = re.compile(r"^[A-Za-z0-9-]+$")


class ApplicantIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    promethee_handle: str | None = Field(default=None, max_length=60)
    github_handle: str | None = Field(default=None, max_length=60)
    roles: list[str] = Field(min_length=1)
    availability: str
    motivation: str | None = Field(default=None, max_length=1200)
    source: str | None = Field(default=None, max_length=60)
    #: Piege a robots : un humain ne voit jamais ce champ.
    website: str | None = None

    @field_validator("roles")
    @classmethod
    def known_roles(cls, v: list[str]) -> list[str]:
        unknown = set(v) - ROLES
        if unknown:
            raise ValueError(f"domaine inconnu : {', '.join(sorted(unknown))}")
        return v

    @field_validator("availability")
    @classmethod
    def known_availability(cls, v: str) -> str:
        if v not in AVAILABILITY:
            raise ValueError("disponibilite inconnue")
        return v

    @field_validator("github_handle")
    @classmethod
    def valid_github(cls, v: str | None) -> str | None:
        if v and not GITHUB_RE.match(v):
            raise ValueError("identifiant GitHub invalide")
        return v

    @field_validator("website")
    @classmethod
    def honeypot_must_stay_empty(cls, v: str | None) -> str | None:
        if v:
            raise ValueError("requete rejetee")
        return v


class SessionIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    handle: str | None = Field(default=None, max_length=60)
    minutes: int = Field(ge=10, le=960)
    probes: int | None = Field(default=None, ge=2, le=20)


class EventIn(BaseModel):
    t: float
    type: Literal["move", "down", "up"]
    code: str | None = Field(default=None, max_length=40)
    x: float | None = None
    y: float | None = None


class ProbeAnswerIn(BaseModel):
    events: list[EventIn] = Field(min_length=1, max_length=4000)
    pasted: bool = False
    reaction_ms: float | None = Field(default=None, ge=0)
    difficulty: float | None = Field(default=None, ge=0, le=10)
    typed_chars: int | None = Field(default=None, ge=0, le=2000)
    expected_chars: int | None = Field(default=None, ge=0, le=2000)
    adjacent_errors: int | None = Field(default=None, ge=0, le=2000)
    backspaces: int | None = Field(default=None, ge=0, le=2000)
    reading_ms: float | None = Field(default=None, ge=0)
    reading_words: int | None = Field(default=None, ge=0, le=500)
    input_mode: Literal["pointer", "touch"] = "pointer"

    def as_events(self) -> list[dict[str, Any]]:
        return [e.model_dump(exclude_none=True) for e in self.events]


class PushKeys(BaseModel):
    #: Non filtrees, des cles illisibles faisaient remonter un binascii.Error
    #: depuis pywebpush jusqu'a arreter le repartiteur : un seul abonnement
    #: bancal suffisait a couper TOUTES les notifications.
    p256dh: str = Field(min_length=16, max_length=255)
    auth: str = Field(min_length=16, max_length=255)

    @field_validator("p256dh", "auth")
    @classmethod
    def decodable_base64url(cls, v: str) -> str:
        padded = v + "=" * (-len(v) % 4)
        try:
            # validate=True : sans lui, base64 ignore silencieusement les
            # caracteres hors alphabet et accepte n'importe quoi.
            base64.b64decode(padded, altchars=b"-_", validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("cle push illisible : base64url attendu") from exc
        return v


class SubscriptionIn(BaseModel):
    endpoint: str = Field(min_length=12, max_length=1000)
    keys: PushKeys

    @field_validator("endpoint")
    @classmethod
    def https_endpoint(cls, v: str) -> str:
        if not v.startswith("https://"):
            raise ValueError("endpoint push invalide : une URL https est attendue")
        return v
