"""Chaine Web Push : abonnements, purge, entetes."""

import uuid
from datetime import timedelta
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.orm import Session

from deciban.models.entities import Probe, PushSubscription, WorkSession, utcnow
from deciban.services import notifier


def _session_with_probe(db: Session) -> Probe:
    start = utcnow()
    session = WorkSession(
        token=str(uuid.uuid4()),
        slug=uuid.uuid4().hex[:8],
        starts_at=start,
        ends_at=start + timedelta(hours=1),
        probe_count=1,
    )
    db.add(session)
    db.flush()
    probe = Probe(
        work_session_id=session.id,
        token=str(uuid.uuid4()),
        fire_at=start,
        status="fired",
        notified_at=start,
    )
    db.add(probe)
    db.commit()
    return probe


def _subscribe(db: Session, probe: Probe, endpoint: str) -> None:
    db.add(
        PushSubscription(
            work_session_id=probe.work_session_id,
            endpoint=endpoint,
            p256dh="cle-publique",
            auth="secret",
        )
    )
    db.commit()


def test_sans_abonnement_rien_n_est_envoye(db_session: Session) -> None:
    probe = _session_with_probe(db_session)
    assert notifier.notify(db_session, probe) == 0


def test_la_charge_transporte_le_jeton_et_la_fenetre(db_session: Session) -> None:
    probe = _session_with_probe(db_session)
    _subscribe(db_session, probe, "https://push.example/a")

    with patch("pywebpush.webpush") as sent:
        notifier.notify(db_session, probe)

    payload = sent.call_args.kwargs["data"]
    assert probe.token in payload
    assert str(Probe.WINDOW) in payload


def test_le_controle_part_avec_une_duree_de_vie_et_une_urgence(db_session: Session) -> None:
    """Un TTL de zero perdrait le controle au moindre hoquet reseau."""
    probe = _session_with_probe(db_session)
    _subscribe(db_session, probe, "https://push.example/b")

    with patch("pywebpush.webpush") as sent:
        notifier.notify(db_session, probe)

    kwargs = sent.call_args.kwargs
    assert kwargs["ttl"] == Probe.WINDOW
    assert kwargs["headers"]["Urgency"] == "high"


def test_chaque_abonnement_de_la_session_est_notifie(db_session: Session) -> None:
    probe = _session_with_probe(db_session)
    for i in range(3):
        _subscribe(db_session, probe, f"https://push.example/{i}")

    with patch("pywebpush.webpush"):
        assert notifier.notify(db_session, probe) == 3


def test_un_abonnement_revoque_est_supprime(db_session: Session) -> None:
    """Sinon on pousse indefiniment vers une adresse morte."""
    probe = _session_with_probe(db_session)
    _subscribe(db_session, probe, "https://push.example/mort")

    from pywebpush import WebPushException

    class Gone:
        status_code = 410

    with patch("pywebpush.webpush", side_effect=WebPushException("parti", response=Gone())):
        assert notifier.notify(db_session, probe) == 0

    restants = db_session.scalars(select(PushSubscription)).all()
    assert restants == []


def test_sans_cles_vapid_aucun_envoi_n_est_tente(db_session: Session) -> None:
    probe = _session_with_probe(db_session)
    _subscribe(db_session, probe, "https://push.example/c")

    from deciban.core.config import get_settings

    settings = get_settings()
    saved = settings.vapid_private_key
    settings.vapid_private_key = ""
    try:
        with patch("pywebpush.webpush") as sent:
            assert notifier.notify(db_session, probe) == 0
        sent.assert_not_called()
    finally:
        settings.vapid_private_key = saved
