"""Point d'entree Alembic.

Deux principes, tenus ici :

1. L'URL de la base vient de la configuration de l'application, jamais
   d'alembic.ini. Le fichier .ini est suivi par git ; l'URL contient le mot de
   passe PostgreSQL. Une seule source de verite, et aucun secret dans le depot.

2. Le meme metadata que l'application. `target_metadata` pointe sur le `Base`
   reellement utilise par les modeles : `alembic revision --autogenerate`
   compare donc l'etat de la base a ce que le code declare, sans copie
   intermediaire susceptible de deriver.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import Connection

from deciban.core.config import get_settings
from deciban.core.database import Base
from deciban.models import entities  # noqa: F401  (enregistre les tables sur Base)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Injectee ici plutot qu'ecrite dans alembic.ini : voir le point 1 ci-dessus.
config.set_main_option("sqlalchemy.url", get_settings().database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Genere le SQL sans se connecter (alembic upgrade --sql)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # SQLite ne sait pas modifier une colonne en place : sans ce mode, la
        # moindre migration de type y echouerait. Sans effet sur PostgreSQL.
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _run(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Applique les migrations sur une connexion reelle.

    Deux appelants, deux chemins :

    - `alembic upgrade head` en ligne de commande : aucune connexion n'est
      fournie, on en ouvre une.
    - l'application au demarrage (`deciban.core.schema`) : elle passe SA
      connexion via `config.attributes`, celle qui detient deja le verrou
      consultatif PostgreSQL. Ouvrir une seconde connexion ici reviendrait a
      migrer en dehors du verrou — et les deux processus, API et repartiteur,
      pourraient de nouveau migrer en meme temps.
    """
    injected = config.attributes.get("connection")
    if injected is not None:
        _run(injected)
        return

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        _run(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
