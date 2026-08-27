"""Session SQLAlchemy et base declarative."""

from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from deciban.core.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()

# check_same_thread : necessaire uniquement pour SQLite en developpement.
_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


#: Injection de session, forme annotee : elle evite d'appeler Depends dans
#: une valeur par defaut, ce que les linters signalent a juste titre.
DbSession = Annotated[Session, Depends(get_db)]
