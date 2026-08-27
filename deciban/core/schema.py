"""Creation du schema, partagee par l'API et le repartiteur.

Les deux processus demarrent independamment : celui qui arrive le premier
cree les tables. L'operation est idempotente.

En production, une vraie chaine de migrations devra remplacer cet appel.
Ce n'est pas encore le cas, et c'est une dette assumee.
"""

from deciban.core.database import Base, engine
from deciban.models import entities  # noqa: F401  (enregistre les tables)


def ensure_schema() -> None:
    Base.metadata.create_all(bind=engine)
