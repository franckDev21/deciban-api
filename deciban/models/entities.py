"""Tables du domaine."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from deciban.core.database import Base
from deciban.core.types import UTCDateTime


def utcnow() -> datetime:
    return datetime.now(UTC)


class WorkSession(Base):
    __tablename__ = "work_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    handle: Mapped[str | None] = mapped_column(String(60), index=True, default=None)
    starts_at: Mapped[datetime] = mapped_column(UTCDateTime)
    ends_at: Mapped[datetime] = mapped_column(UTCDateTime)
    probe_count: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="active")
    ip: Mapped[str | None] = mapped_column(String(45), default=None)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    probes: Mapped[list["Probe"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="Probe.fire_at"
    )
    subscriptions: Mapped[list["PushSubscription"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class Probe(Base):
    __tablename__ = "probes"

    #: Fenetre de reponse, en secondes, a partir du declenchement.
    WINDOW = 90

    id: Mapped[int] = mapped_column(primary_key=True)
    work_session_id: Mapped[int] = mapped_column(
        ForeignKey("work_sessions.id", ondelete="CASCADE"), index=True
    )
    token: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    #: Jamais transmis au client : c'est ce qui empeche de programmer sa presence.
    fire_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    notified_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    answered_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    score: Mapped[float | None] = mapped_column(Float, default=None)
    features: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    session: Mapped[WorkSession] = relationship(back_populates="probes")
    labels: Mapped[list["ProbeLabel"]] = relationship(
        back_populates="probe", cascade="all, delete-orphan"
    )


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_session_id: Mapped[int] = mapped_column(
        ForeignKey("work_sessions.id", ondelete="CASCADE"), index=True
    )
    endpoint: Mapped[str] = mapped_column(Text, unique=True)
    p256dh: Mapped[str] = mapped_column(String(255))
    auth: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    session: Mapped[WorkSession] = relationship(back_populates="subscriptions")


class ProbeLabel(Base):
    __tablename__ = "probe_labels"

    id: Mapped[int] = mapped_column(primary_key=True)
    probe_id: Mapped[int] = mapped_column(ForeignKey("probes.id", ondelete="CASCADE"), index=True)
    #: La verite terrain : ce controle venait-il d'un humain ?
    is_human: Mapped[bool] = mapped_column(Boolean)
    #: D'ou vient l'etiquette. Sans cela on ne peut pas juger de sa fiabilite.
    source: Mapped[str] = mapped_column(String(30))
    note: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    probe: Mapped[Probe] = relationship(back_populates="labels")


class Applicant(Base):
    __tablename__ = "applicants"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    promethee_handle: Mapped[str | None] = mapped_column(String(60), default=None)
    github_handle: Mapped[str | None] = mapped_column(String(60), default=None)
    roles: Mapped[list[str]] = mapped_column(JSON)
    availability: Mapped[str] = mapped_column(String(20))
    motivation: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[str] = mapped_column(String(20), default="nouveau", index=True)
    source: Mapped[str | None] = mapped_column(String(60), default=None)
    ip: Mapped[str | None] = mapped_column(String(45), default=None)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Heartbeat(Base):
    """Signal de vie d'un processus annexe.

    Le repartiteur tourne dans un processus separe de l'API : un compteur
    en memoire serait invisible depuis l'autre cote. La base est le seul
    terrain que les deux partagent.
    """

    __tablename__ = "heartbeats"

    name: Mapped[str] = mapped_column(String(40), primary_key=True)
    beat_at: Mapped[datetime] = mapped_column(UTCDateTime)
