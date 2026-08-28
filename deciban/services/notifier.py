"""Envoi des controles par Web Push.

C'est le serveur qui pousse : le navigateur ne demande jamais quand tombera
le prochain controle, donc il ne peut pas l'apprendre.
"""

import json
import logging
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from deciban.core.config import get_settings
from deciban.models.entities import Probe, PushSubscription

logger = logging.getLogger(__name__)


def notify(db: Session, probe: Probe) -> int:
    """Retourne le nombre d'abonnements effectivement notifies."""
    settings = get_settings()
    if not settings.push_configured:
        return 0

    subs = list(
        db.scalars(
            select(PushSubscription).where(
                PushSubscription.work_session_id == probe.work_session_id
            )
        )
    )
    if not subs:
        return 0

    try:
        from pywebpush import WebPushException, webpush
    except ImportError:  # pragma: no cover - dependance absente en test
        logger.warning("pywebpush indisponible")
        return 0

    payload = json.dumps({"probe": probe.token, "window": Probe.WINDOW})
    sent = 0
    expired: list[str] = []

    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=payload,
                vapid_private_key=settings.vapid_private_key,
                vapid_claims={"sub": settings.vapid_subject},
                # Un controle a une duree de vie : livre trop tard il ne
                # sert plus a rien, mais un TTL de zero le perdrait au
                # moindre hoquet reseau.
                ttl=Probe.WINDOW,
                headers={"Urgency": "high"},
            )
            sent += 1
        except WebPushException as exc:  # pragma: no cover - reseau
            status: Any = getattr(exc.response, "status_code", None)
            # Un abonnement revoque doit disparaitre, sinon on pousse
            # indefiniment vers une adresse morte.
            if status in (404, 410):
                expired.append(sub.endpoint)
            else:
                logger.warning("push echoue : %s", exc)
        except Exception as exc:  # pragma: no cover - donnee corrompue
            # Filet de securite. pywebpush leve un binascii.Error, et non une
            # WebPushException, quand les cles d'un abonnement sont illisibles.
            # Sans ce rattrapage l'exception remonte jusqu'a la boucle du
            # repartiteur et l'arrete definitivement.
            logger.warning("abonnement illisible, retire : %s", exc)
            expired.append(sub.endpoint)

    if expired:
        db.execute(delete(PushSubscription).where(PushSubscription.endpoint.in_(expired)))
        db.commit()

    return sent
