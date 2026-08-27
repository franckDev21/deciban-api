"""Infrastructure de calibration : elle mesure, ou elle se tait."""

import uuid
from datetime import timedelta

from sqlalchemy.orm import Session

from deciban.models.entities import Probe, ProbeLabel, WorkSession, utcnow
from deciban.services import calibration, motor
from tests import factories


def _seed(db: Session, count: int, human: bool) -> None:
    start = utcnow() - timedelta(hours=1)
    session = WorkSession(
        token=str(uuid.uuid4()),
        slug=uuid.uuid4().hex[:8],
        handle="humain" if human else "machine",
        starts_at=start,
        ends_at=start + timedelta(hours=2),
        probe_count=count,
    )
    db.add(session)
    db.flush()

    for i in range(count):
        result = (
            motor.score(factories.human(seed=i + 1), reaction_ms=700 + i)
            if human
            else motor.score(factories.script(), pasted=True, reaction_ms=40)
        )
        probe = Probe(
            work_session_id=session.id,
            token=str(uuid.uuid4()),
            fire_at=start + timedelta(minutes=i),
            status="answered",
            answered_at=utcnow(),
            score=result["score"],
            features=result,
        )
        db.add(probe)
        db.flush()
        db.add(ProbeLabel(probe_id=probe.id, is_human=human, source="synthetic"))

    db.commit()


def test_sans_etiquettes_la_calibration_refuse_de_deviner(db_session: Session) -> None:
    report = calibration.report(db_session)
    assert report["ready"] is False
    assert report["signals"] == []
    assert report["separation"] is None
    assert "insuffisantes" in report["status"]


def test_l_endpoint_public_annonce_l_absence_de_validation(client) -> None:
    r = client.get("/api/calibration")
    assert r.status_code == 200
    assert r.json()["ready"] is False
    assert r.json()["labels"]["human"] == 0


def test_en_deca_du_minimum_la_calibration_reste_muette(db_session: Session) -> None:
    _seed(db_session, calibration.MIN_LABELS_PER_CLASS - 1, human=True)
    _seed(db_session, calibration.MIN_LABELS_PER_CLASS - 1, human=False)
    assert calibration.report(db_session)["ready"] is False


def test_avec_assez_d_etiquettes_les_poids_sont_re_estimes(db_session: Session) -> None:
    _seed(db_session, 35, human=True)
    _seed(db_session, 35, human=False)

    report = calibration.report(db_session)
    assert report["ready"] is True
    assert report["signals"]

    tremor = next(s for s in report["signals"] if s["key"] == "tremor")
    assert tremor["estimated_db"] > 0, "le tremblement doit ressortir en faveur de l'humain"


def test_la_separation_mesure_les_faux_positifs_a_detection_fixee(db_session: Session) -> None:
    _seed(db_session, 35, human=True)
    _seed(db_session, 35, human=False)

    separation = calibration.report(db_session)["separation"]
    assert separation["true_positive_rate"] == 0.95
    assert separation["false_positive_rate"] < 0.2
