# Deciban · API

Moteur de preuve d'humanité, fondé sur l'accumulation de rapports de vraisemblance exprimés en **decibans**.

FastAPI · SQLAlchemy 2 · Pydantic v2 · scipy · Python 3.12

---

## Démarrer

### Avec Docker, recommandé

Depuis la racine du dépôt :

```bash
docker compose up --build api dispatcher
```

### En local

```bash
cd api-py
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env
```

Générez les clés VAPID et recopiez-les dans `.env` :

```bash
.venv/bin/python -c "
import base64
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
k = ec.generate_private_key(ec.SECP256R1())
b = lambda x: base64.urlsafe_b64encode(x).decode().rstrip('=')
pub = k.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
print('VAPID_PUBLIC_KEY=' + b(pub))
print('VAPID_PRIVATE_KEY=' + b(k.private_numbers().private_value.to_bytes(32, 'big')))
"
```

Puis **deux terminaux** :

```bash
.venv/bin/uvicorn deciban.main:app --reload --port 8000
```

```bash
.venv/bin/python -m deciban.dispatcher --watch
```

> Le second n'est pas optionnel. Le répartiteur est le seul processus qui déclenche les contrôles et qui envoie les notifications. Sans lui, l'API répond mais rien ne se passe jamais.

Documentation interactive : <http://localhost:8000/docs>

---

## Variables d'environnement

| Variable | Défaut | Rôle |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./deciban.sqlite` | Chaîne SQLAlchemy. PostgreSQL en production. |
| `FRONTEND_URLS` | `http://localhost:3000` | Origines autorisées par CORS, séparées par des virgules. |
| `VAPID_SUBJECT` | `mailto:contact@deciban.local` | Contact déclaré au service de push. |
| `VAPID_PUBLIC_KEY` | vide | Transmise au navigateur pour l'abonnement. |
| `VAPID_PRIVATE_KEY` | vide | **Secret.** Signe les notifications au nom du service. |

Sans clés VAPID, l'API démarre normalement mais `push_configured` reste à `false` et l'appel ne fonctionne que dans un onglet resté ouvert.

---

## Points d'entrée

| Méthode | Route | Rôle |
|---|---|---|
| `POST` | `/api/sessions` | Ouvre une fenêtre et tire les contrôles **en secret** |
| `GET` | `/api/sessions/{token}` | État de la session, et contrôle en cours s'il y en a un |
| `POST` | `/api/probes/{token}` | Reçoit la trace d'un contrôle, la mesure, rend la preuve |
| `POST` | `/api/sessions/{token}/subscribe` | Enregistre l'abonnement Web Push du navigateur |
| `GET` | `/api/attestations/{slug}` | Attestation publique, sans aucun secret de session |
| `GET` | `/api/calibration` | État de validation des poids, publié pour être contesté |
| `GET` | `/api/health` | Le répartiteur tourne-t-il vraiment |
| `GET` | `/api/vapid` | Clé publique nécessaire à l'abonnement |
| `POST` | `/api/applicants` | Inscription à l'équipe, avec piège à robots |

### Exemple complet

```bash
# 1. Ouvrir une fenêtre de 15 minutes avec 3 contrôles
curl -X POST http://localhost:8000/api/sessions \
  -H 'Content-Type: application/json' \
  -d '{"handle":"Franck","minutes":15,"probes":3}'
# → {"token":"…","slug":"k7ilddr9","probe_count":3,"vapid_public_key":"…"}

# 2. Consulter l'état. « due » est non nul quand un contrôle est ouvert.
curl http://localhost:8000/api/sessions/<token>

# 3. Répondre à un contrôle
curl -X POST http://localhost:8000/api/probes/<probe_token> \
  -H 'Content-Type: application/json' \
  -d '{"events":[{"t":0,"type":"move","x":10,"y":10}],"reaction_ms":780}'

# 4. Attestation publique
curl http://localhost:8000/api/attestations/k7ilddr9
```

**La réponse d'ouverture ne contient aucun horaire de contrôle**, et `GET /api/sessions/{token}` répond toujours `"next": "inconnu, par conception"`. C'est ce qui empêche quelqu'un de programmer sa présence. Un test le vérifie.

---

## Architecture

```
deciban/
├── core/
│   ├── config.py      configuration lue depuis l'environnement
│   ├── database.py    session SQLAlchemy, injection annotée
│   ├── types.py       UTCDateTime : SQLite ne conserve aucun fuseau
│   └── schema.py      création du schéma, partagée par les deux processus
├── models/entities.py tables du domaine
├── schemas/payloads.py validation Pydantic, piège à robots compris
├── services/
│   ├── coverage.py    ±15 db · loi Bêta, quantiles exacts
│   ├── rhythm.py      ±12 db · dette de sommeil, rebond
│   ├── provenance.py  ±10 db · frappé ou collé, révisions
│   ├── cognition.py   ±8 db  · latence contre difficulté
│   ├── motor.py       ±8 db  · passe-bande 8–12 Hz
│   ├── report.py      assemblage des familles et verdict
│   ├── calibration.py ré-estimation sur données étiquetées
│   └── notifier.py    envoi Web Push
├── routes/            points d'entrée HTTP
└── dispatcher.py      déclenchement des contrôles
```

### Deux calculs qui ne tolèrent aucune approximation

**L'intervalle de couverture** repose sur une loi Bêta souvent très asymétrique. Sur deux ou trois contrôles, l'approximer par une gaussienne donne un intervalle faux, parfois hors de `[0, 1]`. Le code utilise `scipy.stats.beta.ppf`.

**Le tremblement** se mesure entre 8 et 12 Hz. Les événements du navigateur arrivant à pas irrégulier, le signal est interpolé sur une grille à 100 Hz, puis analysé par densité spectrale de Welch. Le résultat est un **rapport de puissance**, donc sans unité et comparable d'une machine à l'autre.

---

## Tests

```bash
.venv/bin/pytest                       # 62 tests
.venv/bin/pytest --cov=deciban         # avec couverture
.venv/bin/ruff check deciban tests     # style
.venv/bin/ruff format --check deciban tests
```

Ce que la suite couvre, au-delà du chemin nominal :

- séparation entre trace humaine et trace de script, au moins dix decibans
- **un signal sans données contribue zéro, jamais une pénalité**
- l'écrêtage de famille fonctionne dans les deux sens
- l'attestation publique ne divulgue ni le jeton ni les horaires
- la calibration refuse de deviner en dessous de trente étiquettes par classe
- un abonnement push révoqué est supprimé

---

## Dette technique assumée

- **Pas de migrations.** Le schéma est créé au démarrage. Une chaîne Alembic est à ajouter avant la production sérieuse.
- **Poids non calibrés.** Ils sont plausibles, pas mesurés. `GET /api/calibration` le dit publiquement.
- **Deux familles inertes.** La corrélation latence-difficulté ne fonctionnera que lorsque le défi proposera plusieurs niveaux de difficulté. La famille des pièges n'est pas implémentée.

---

## Contribuer

Voir [CONTRIBUTING.md](../CONTRIBUTING.md) à la racine du dépôt.
