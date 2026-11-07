# ==============================================================================
# Daily Hadith AI Agent — Multi-Stage Production Dockerfile
#
# Stage 1: Build & Dependency Resolution (Wheel compilation)
# Stage 2: Minimal, Unprivileged Production Runtime (~160MB, non-root user)
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Builder
# ------------------------------------------------------------------------------
FROM python:3.13-slim AS builder

WORKDIR /build

# Install minimal compilation tools required for binary wheels (e.g., psycopg)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create isolated build virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install dependencies into /opt/venv
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt


# ------------------------------------------------------------------------------
# Stage 2: Final Production Runtime
# ------------------------------------------------------------------------------
FROM python:3.13-slim AS runtime

# Security & environment hardening
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8080 \
    APP_ENV=production

WORKDIR /app

# Install runtime dependencies only (curl for container healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create unprivileged service user and group (UID/GID 10001)
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/sh -d /app appuser

# Copy pre-built virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy application source code and configuration
COPY --chown=appuser:appgroup alembic.ini pyproject.toml ./
COPY --chown=appuser:appgroup alembic/ ./alembic/
COPY --chown=appuser:appgroup src/ ./src/

# Switch to unprivileged runtime user
USER appuser:appgroup

# Container metadata & networking
EXPOSE 8080

# Built-in container healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8080}/health || exit 1

# Default command: Start unified FastAPI server with dynamic PORT resolution
CMD ["sh", "-c", "exec uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
