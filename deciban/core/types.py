"""Type de date garantissant l'UTC dans les deux sens.

SQLite ne conserve aucun fuseau : sans ce decorateur, une date relue
revient naive et toute comparaison avec un datetime conscient echoue.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator):
    """Stocke en UTC naif, relit en UTC conscient."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            # Une date sans fuseau est consideree deja en UTC.
            return value
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: Any | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
