# ==============================================================================
# STAGE 1: Builder - Install dependencies and download ML models
# ==============================================================================
FROM python:3.11-slim as builder

# Set environment variables
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

# Create app directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --user --no-warn-script-location -r requirements.txt

# Download ML models (sentence-transformers) to avoid downloading in each container
# COMMENTED: Causes version conflicts during build. Model downloads on first use instead.
# RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# ==============================================================================
# STAGE 2: Runtime - Minimal production image
# ==============================================================================
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/root/.local/bin:$PATH \
    DJANGO_SETTINGS_MODULE=lti_recommender_project.settings_docker

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    libpq5 \
    openssl \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -u 1000 django && \
    mkdir -p /app /app/staticfiles /app/media /app/logs /app/keys /app/ml/saved_models && \
    chown -R django:django /app

# Set working directory
WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder --chown=django:django /root/.local /root/.local
# Note: .cache directory removed - models download on first use

# Copy application code
COPY --chown=django:django . .

# Copy and set permissions for scripts
COPY --chown=django:django scripts/ /app/scripts/
RUN chmod +x /app/scripts/*.sh

# Create volume mount points
VOLUME ["/app/staticfiles", "/app/media", "/app/logs", "/app/keys"]

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/admin/ || exit 1

# Switch to non-root user
USER django

# Set entrypoint
ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]

# Default command - run gunicorn
CMD ["gunicorn", "lti_recommender_project.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "info"]
