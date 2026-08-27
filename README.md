# API Deciban

Moteur de preuve d'humanité fondé sur l'accumulation de rapports de
vraisemblance, exprimés en decibans.

## Démarrer

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env          # puis générer les clés VAPID
.venv/bin/uvicorn deciban.main:app --reload --port 8000
```

Dans un second terminal, **sans lequel aucun contrôle ne se déclenche** :

```bash
.venv/bin/python -m deciban.dispatcher --watch
```

Documentation interactive sur <http://localhost:8000/docs>.

## Tests

```bash
.venv/bin/pytest              # 56 tests
.venv/bin/ruff check deciban tests
.venv/bin/ruff format --check deciban tests
```

## Structure

| Chemin | Rôle |
|---|---|
| `deciban/services/coverage.py` | Couverture attestée, loi Bêta exacte, plafond ±15 db |
| `deciban/services/rhythm.py` | Rythme de vie, dette de sommeil sur 21 jours, ±12 db |
| `deciban/services/provenance.py` | Provenance du travail, ±10 db |
| `deciban/services/cognition.py` | Cognition, ±8 db |
| `deciban/services/motor.py` | Signature motrice, passe-bande 8–12 Hz, ±8 db |
| `deciban/services/report.py` | Assemblage des familles et verdict |
| `deciban/services/calibration.py` | Ré-estimation des poids sur données étiquetées |
| `deciban/dispatcher.py` | Déclenchement des contrôles et envoi Web Push |

## Ce que le code ne fait pas

Les poids sont une **calibration initiale plausible, non validée**. Aucun
chiffre de performance ne peut être revendiqué tant que `/api/calibration`
répond `ready: false`. C'est délibéré, et c'est publié pour être contesté.
