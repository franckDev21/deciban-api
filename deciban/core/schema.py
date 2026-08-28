"""Mise a jour du schema, partagee par l'API et le repartiteur.

Les deux processus demarrent independamment et appellent tous les deux cette
fonction. Elle doit donc rester sure quand deux appels se croisent.

Deux comportements, selon le moteur :

- **PostgreSQL (production)** : la chaine Alembic est appliquee
  (`alembic upgrade head`). C'est le seul mode qui sait MODIFIER une table
  existante — ajouter une colonne a une base qui contient deja des donnees.

- **SQLite (developpement, tests)** : `create_all`, comme avant. Les 62 tests
  montent une base neuve en memoire a chaque cas ; y faire tourner la chaine
  de migrations les ralentirait sans rien prouver de plus, puisque la base est
  jetee juste apres. Le compromis est assume et il a un cout : une migration
  fausse ne se revele qu'au premier deploiement PostgreSQL. C'est pour cela
  que la migration de reference a ete generee par autogenerate contre une
  vraie base PostgreSQL vide, et non ecrite a la main.
"""

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from deciban.core.database import Base, engine
from deciban.models import entities  # noqa: F401  (enregistre les tables)

logger = logging.getLogger(__name__)

#: Racine du projet : ce fichier est <racine>/deciban/core/schema.py.
_ROOT = Path(__file__).resolve().parents[2]

#: Cle du verrou consultatif PostgreSQL. Valeur arbitraire, mais elle doit
#: rester IDENTIQUE entre l'API et le repartiteur — c'est ce qui les empeche de
#: migrer en meme temps. Ne pas la changer sans raison.
_LOCK_KEY = 8147236591


def _alembic_config() -> Config:
    cfg = Config(str(_ROOT / "alembic.ini"))
    # Chemin absolu : sans cela, Alembic cherche « migrations/ » a partir du
    # repertoire courant du processus, qui n'est pas garanti.
    cfg.set_main_option("script_location", str(_ROOT / "migrations"))
    return cfg


def ensure_schema() -> None:
    if engine.dialect.name == "sqlite":
        Base.metadata.create_all(bind=engine)
        return

    with engine.connect() as connection:
        # Verrou consultatif : l'API et le repartiteur demarrent ensemble et
        # appelleraient tous les deux `upgrade`. Le premier arrive prend le
        # verrou, le second ATTEND ici puis ne trouve plus rien a faire. Sans
        # ce verrou, deux « CREATE TABLE » simultanes se percutent et l'un des
        # deux conteneurs meurt au demarrage.
        #
        # C'est un verrou de session, pas de transaction : il tient tant que
        # cette connexion vit, y compris a travers les commits que fait
        # Alembic. Il est relache explicitement dans le finally.
        connection.execute(text("SELECT pg_advisory_lock(:k)"), {"k": _LOCK_KEY})
        try:
            cfg = _alembic_config()
            # La connexion est passee a env.py pour que la migration se fasse
            # SOUS le verrou. En ouvrir une autre la-bas viderait le verrou de
            # son sens.
            cfg.attributes["connection"] = connection
            command.upgrade(cfg, "head")
            logger.info("Schema a jour (alembic upgrade head).")
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": _LOCK_KEY})
