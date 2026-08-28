"""Fixtures : une base neuve et isolee pour chaque test."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from deciban.core.config import get_settings
from deciban.core.database import Base, get_db
from deciban.main import create_app


@pytest.fixture(autouse=True)
def vapid_configured() -> Generator[None, None, None]:
    """Cles de test explicites.

    Sans cela, la suite dependrait d'un .env present sur la machine :
    elle passerait en local et echouerait en integration continue.
    """
    settings = get_settings()
    saved = (settings.vapid_public_key, settings.vapid_private_key)
    settings.vapid_public_key = "cle-publique-de-test"
    settings.vapid_private_key = "cle-privee-de-test"
    try:
        yield
    finally:
        settings.vapid_public_key, settings.vapid_private_key = saved


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    maker = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
    session = maker()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
