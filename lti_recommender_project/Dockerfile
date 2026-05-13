# ==============================================================================
# STAGE 1: Builder - Install dependencies
# ==============================================================================
FROM python:3.11-slim as builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    postgresql-client \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Install Python dependencies
COPY requirements.txt .
RUN pip install --user --no-warn-script-location -r requirements.txt

# ==============================================================================
# STAGE 2: Runtime - Minimal production image
# ==============================================================================
FROM python:3.11-slim

# --------------------------------------------------------------------------
# /srv/lti_recommender_project/ → importable as `lti_recommender_project`
# /app/                         → mutable data: staticfiles, media, logs, keys
# --------------------------------------------------------------------------
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/home/django/.local/bin:$PATH \
    PYTHONPATH=/srv \
    DJANGO_SETTINGS_MODULE=lti_recommender_project.settings_docker

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    libpq5 \
    openssl \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user and required directories
RUN useradd -m -u 1000 django && \
    mkdir -p /srv/lti_recommender_project \
             /app/staticfiles \
             /app/media \
             /app/logs \
             /app/keys \
             /app/ml/saved_models && \
    chown -R django:django /srv /app

# Copy Python packages from builder (owned by django)
COPY --from=builder --chown=django:django /root/.local /home/django/.local

# Copy application code into the importable package location
WORKDIR /srv/lti_recommender_project
COPY --chown=django:django . .

# Create symlinks so scripts and data dirs work from the project root
RUN ln -sf /app/staticfiles /srv/lti_recommender_project/staticfiles && \
    ln -sf /app/media       /srv/lti_recommender_project/media       && \
    ln -sf /app/logs        /srv/lti_recommender_project/logs        && \
    ln -sf /app/keys        /srv/lti_recommender_project/keys

# Make entrypoint scripts executable
RUN chmod +x /srv/lti_recommender_project/scripts/*.sh

# Default working directory for manage.py commands
WORKDIR /srv/lti_recommender_project

# Volume mount points for mutable data
VOLUME ["/app/staticfiles", "/app/media", "/app/logs", "/app/keys"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/admin/ || exit 1

USER django

ENTRYPOINT ["/srv/lti_recommender_project/scripts/docker-entrypoint.sh"]

CMD ["gunicorn", "lti_recommender_project.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", \
     "--timeout", "300", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "info"]
