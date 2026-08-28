"""Schema initial — photographie de l'existant.

Cette migration ne cree rien de nouveau : elle decrit le schema tel qu'il
existait deja le 2026-08-28, construit jusque-la par `Base.metadata.create_all`
au demarrage de l'application.

La base de production N'A PAS exécuté cette migration : elle a ete marquee
comme deja a jour (`alembic stamp 0001`), ce qui est la procedure normale
quand on adopte Alembic sur une base peuplee. Rejouer un CREATE TABLE sur des
tables existantes aurait echoue.

Elle sert a deux choses :
  - une base neuve (poste de developpement, integration continue) obtient le
    bon schema par `alembic upgrade head`, sans create_all ;
  - elle donne un point de depart aux migrations suivantes.

Revision ID: 0001
Revise : (aucune — c'est la premiere)
Cree le : 2026-08-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Indispensable : les colonnes de dates ci-dessous sont declarees
# « deciban.core.types.UTCDateTime() ». L'autogenerate d'Alembic ecrit ce nom
# complet sans ajouter l'import — sans cette ligne, la migration plante sur un
# NameError. Voir aussi migrations/script.py.mako.
import deciban.core.types  # noqa: F401

revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('applicants',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('email', sa.String(length=180), nullable=False),
    sa.Column('promethee_handle', sa.String(length=60), nullable=True),
    sa.Column('github_handle', sa.String(length=60), nullable=True),
    sa.Column('roles', sa.JSON(), nullable=False),
    sa.Column('availability', sa.String(length=20), nullable=False),
    sa.Column('motivation', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('source', sa.String(length=60), nullable=True),
    sa.Column('ip', sa.String(length=45), nullable=True),
    sa.Column('created_at', deciban.core.types.UTCDateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('applicants', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_applicants_email'), ['email'], unique=True)
        batch_op.create_index(batch_op.f('ix_applicants_status'), ['status'], unique=False)

    op.create_table('heartbeats',
    sa.Column('name', sa.String(length=40), nullable=False),
    sa.Column('beat_at', deciban.core.types.UTCDateTime(), nullable=False),
    sa.PrimaryKeyConstraint('name')
    )
    op.create_table('work_sessions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('token', sa.String(length=36), nullable=False),
    sa.Column('slug', sa.String(length=12), nullable=False),
    sa.Column('handle', sa.String(length=60), nullable=True),
    sa.Column('starts_at', deciban.core.types.UTCDateTime(), nullable=False),
    sa.Column('ends_at', deciban.core.types.UTCDateTime(), nullable=False),
    sa.Column('probe_count', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('ip', sa.String(length=45), nullable=True),
    sa.Column('created_at', deciban.core.types.UTCDateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('work_sessions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_work_sessions_handle'), ['handle'], unique=False)
        batch_op.create_index(batch_op.f('ix_work_sessions_slug'), ['slug'], unique=True)
        batch_op.create_index(batch_op.f('ix_work_sessions_token'), ['token'], unique=True)

    op.create_table('probes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('work_session_id', sa.Integer(), nullable=False),
    sa.Column('token', sa.String(length=36), nullable=False),
    sa.Column('fire_at', deciban.core.types.UTCDateTime(), nullable=False),
    sa.Column('notified_at', deciban.core.types.UTCDateTime(), nullable=True),
    sa.Column('answered_at', deciban.core.types.UTCDateTime(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('score', sa.Float(), nullable=True),
    sa.Column('features', sa.JSON(), nullable=True),
    sa.Column('created_at', deciban.core.types.UTCDateTime(), nullable=False),
    sa.ForeignKeyConstraint(['work_session_id'], ['work_sessions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('probes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_probes_fire_at'), ['fire_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_probes_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_probes_token'), ['token'], unique=True)
        batch_op.create_index(batch_op.f('ix_probes_work_session_id'), ['work_session_id'], unique=False)

    op.create_table('push_subscriptions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('work_session_id', sa.Integer(), nullable=False),
    sa.Column('endpoint', sa.Text(), nullable=False),
    sa.Column('p256dh', sa.String(length=255), nullable=False),
    sa.Column('auth', sa.String(length=255), nullable=False),
    sa.Column('created_at', deciban.core.types.UTCDateTime(), nullable=False),
    sa.ForeignKeyConstraint(['work_session_id'], ['work_sessions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('endpoint')
    )
    with op.batch_alter_table('push_subscriptions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_push_subscriptions_work_session_id'), ['work_session_id'], unique=False)

    op.create_table('probe_labels',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('probe_id', sa.Integer(), nullable=False),
    sa.Column('is_human', sa.Boolean(), nullable=False),
    sa.Column('source', sa.String(length=30), nullable=False),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('created_at', deciban.core.types.UTCDateTime(), nullable=False),
    sa.ForeignKeyConstraint(['probe_id'], ['probes.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('probe_labels', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_probe_labels_probe_id'), ['probe_id'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('probe_labels', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_probe_labels_probe_id'))

    op.drop_table('probe_labels')
    with op.batch_alter_table('push_subscriptions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_push_subscriptions_work_session_id'))

    op.drop_table('push_subscriptions')
    with op.batch_alter_table('probes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_probes_work_session_id'))
        batch_op.drop_index(batch_op.f('ix_probes_token'))
        batch_op.drop_index(batch_op.f('ix_probes_status'))
        batch_op.drop_index(batch_op.f('ix_probes_fire_at'))

    op.drop_table('probes')
    with op.batch_alter_table('work_sessions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_work_sessions_token'))
        batch_op.drop_index(batch_op.f('ix_work_sessions_slug'))
        batch_op.drop_index(batch_op.f('ix_work_sessions_handle'))

    op.drop_table('work_sessions')
    op.drop_table('heartbeats')
    with op.batch_alter_table('applicants', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_applicants_status'))
        batch_op.drop_index(batch_op.f('ix_applicants_email'))

    op.drop_table('applicants')
