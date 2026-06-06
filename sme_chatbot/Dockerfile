# =========================================================================
# SME Chatbot — production image.
#
# Single image, two entry points:
#     web    : uvicorn app.main:app    (the FastAPI server)
#     worker : python -m app.workers.worker  (the RQ background worker)
#
# Pick the entry point at container start time via $SERVICE_ROLE.
#
# Build context:
#     docker build -t sme-chatbot ./final_year_project/sme_chatbot
# =========================================================================

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
        ca-certificates \
        && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependency install — copy pyproject first so the layer is cacheable.
COPY pyproject.toml ./
RUN pip install --upgrade pip && \
    pip install --no-cache-dir \
        "fastapi==0.115.*" "uvicorn[standard]==0.30.*" "gunicorn==23.*" \
        "pydantic==2.*" "pydantic-settings==2.*" \
        "psycopg[binary,pool]==3.2.*" "alembic==1.13.*" "sqlalchemy==2.*" \
        "redis==5.*" "rq==1.16.*" \
        "pymilvus==2.4.*" "sentence-transformers==3.*" \
        "groq==0.11.*" "httpx==0.27.*" \
        "pypdf==4.*" "python-docx==1.*" "openpyxl==3.*" "pandas==2.*" \
        "boto3==1.34.*" \
        "python-dotenv==1.*" "python-multipart==0.0.*" "tenacity==8.*" \
        "structlog==24.*"

# Application code.
COPY engine    ./engine
COPY core      ./core
COPY adapters  ./adapters
COPY app       ./app
COPY scripts   ./scripts
COPY migrations ./migrations

EXPOSE 8000

# Default to the web role; the worker overrides this in render.yaml.
ENV SERVICE_ROLE=web

COPY <<'EOF' /app/start.sh
#!/usr/bin/env sh
set -e

# Apply the (idempotent) schema before the web role starts serving. Every
# CREATE in migrations/001_initial.sql uses IF NOT EXISTS, so running this on
# each boot is safe and keeps the production DB in sync without a manual step.
if [ "${SERVICE_ROLE:-web}" = "web" ] && [ -n "${DATABASE_URL}" ]; then
    echo "[start] applying database migrations ..."
    python scripts/apply_migrations.py || {
        echo "[start] migration step failed; continuing to boot" >&2
    }
fi

case "${SERVICE_ROLE:-web}" in
    web)
        exec gunicorn app.main:app \
            -k uvicorn.workers.UvicornWorker \
            -b 0.0.0.0:${PORT:-8000} \
            --workers ${WEB_CONCURRENCY:-2} \
            --timeout 60 \
            --access-logfile - \
            --error-logfile -
        ;;
    worker)
        exec python -m app.workers.worker --queues whatsapp ingestion
        ;;
    *)
        echo "Unknown SERVICE_ROLE: ${SERVICE_ROLE}" >&2
        exit 64
        ;;
esac
EOF
RUN chmod +x /app/start.sh

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:${PORT:-8000}/health || exit 1

CMD ["/app/start.sh"]
