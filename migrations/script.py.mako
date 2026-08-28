"""${message}

Revision ID: ${up_revision}
Revise : ${down_revision | comma,n}
Cree le : ${create_date}
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Les modeles utilisent UTCDateTime, un type maison. `alembic revision
# --autogenerate` ecrit « deciban.core.types.UTCDateTime() » dans les
# migrations mais n'ajoute PAS l'import correspondant : sans cette ligne, la
# migration plante sur un NameError au moment de s'appliquer. L'import est
# donc place ici, dans le gabarit, pour que le probleme ne se repose pas.
import deciban.core.types  # noqa: F401

revision: str = ${repr(up_revision)}
down_revision: str | None = ${repr(down_revision)}
branch_labels: str | Sequence[str] | None = ${repr(branch_labels)}
depends_on: str | Sequence[str] | None = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
