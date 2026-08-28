# syntax=docker/dockerfile:1

# ── Etape de construction ────────────────────────────────────────────────
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# scipy et numpy ont besoin d'une chaine de compilation si aucune roue
# precompilee n'existe pour l'architecture cible.
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential gcc \
 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY deciban ./deciban

RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --upgrade pip \
 && /opt/venv/bin/pip install .

# ── Image finale ─────────────────────────────────────────────────────────
FROM python:3.12-slim

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# On ne tourne jamais en root : une faille dans l'application ne doit pas
# donner les pleins pouvoirs sur le conteneur.
RUN useradd --create-home --shell /usr/sbin/nologin deciban

# Le repertoire de donnees doit exister ET appartenir a l'utilisateur AVANT
# le montage : un volume nomme herite des droits du dossier present dans
# l'image. Sans cela il arrive en root et le processus ne peut pas ecrire.
RUN mkdir -p /data && chown deciban:deciban /data
VOLUME ["/data"]

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=deciban:deciban deciban ./deciban
COPY --chown=deciban:deciban pyproject.toml ./

# La chaine de migrations doit voyager AVEC l'application : c'est elle qui met
# le schema a jour au demarrage. Oubliee ici, l'image se lance mais ne trouve
# pas ses migrations, et une base neuve reste vide.
COPY --chown=deciban:deciban alembic.ini ./
COPY --chown=deciban:deciban migrations ./migrations

USER deciban
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).status==200 else 1)"

CMD ["uvicorn", "deciban.main:app", "--host", "0.0.0.0", "--port", "8000"]
