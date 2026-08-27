"""Declenche les controles arrives a echeance et expire ceux sans reponse.

En production : planifie chaque minute, ou lance avec --watch.
Sans ce processus, aucun controle ne se declenche jamais.

    python -m deciban.dispatcher --watch
"""

import argparse
import logging
import time

from sqlalchemy import select

from deciban.core.database import SessionLocal
from deciban.models.entities import Probe, utcnow
from deciban.routes.system import touch
from deciban.services.notifier import notify

logger = logging.getLogger("deciban.dispatcher")


def run_once() -> tuple[int, int]:
    """Retourne (controles declenches, controles expires)."""
    fired = 0
    expired = 0

    with SessionLocal() as db:
        touch(db)
        now = utcnow()

        due = db.scalars(select(Probe).where(Probe.status == "pending", Probe.fire_at <= now)).all()
        for probe in due:
            probe.status = "fired"
            probe.notified_at = now
            db.commit()
            sent = notify(db, probe)
            fired += 1
            logger.info("controle %s declenche, %d notification(s)", probe.token[:8], sent)

        stale = db.scalars(
            select(Probe).where(Probe.status == "fired", Probe.answered_at.is_(None))
        ).all()
        for probe in stale:
            reference = probe.notified_at or probe.fire_at
            if (utcnow() - reference).total_seconds() > Probe.WINDOW:
                probe.status = "missed"
                expired += 1
                logger.info("controle %s manque", probe.token[:8])
        db.commit()

    return fired, expired


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watch", action="store_true", help="boucle toutes les dix secondes")
    parser.add_argument("--interval", type=int, default=10)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s", datefmt="%H:%M:%S")

    if not args.watch:
        run_once()
        return

    logger.info("Surveillance des controles. Ctrl+C pour arreter.")
    try:
        while True:
            run_once()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        logger.info("Arret.")


if __name__ == "__main__":
    main()
