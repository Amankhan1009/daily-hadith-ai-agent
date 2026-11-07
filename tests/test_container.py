"""
Automated Unit Tests for Docker Containerization & Healthcheck Invariants.

Verifies:
1. Multi-stage Dockerfile structural validity and security constraints.
2. Non-root user enforcement (USER appuser).
3. Docker ignore security exclusions (.env, .venv, .git).
4. Local Docker Compose service configuration.
5. Container healthcheck endpoint compatibility.
"""

from pathlib import Path

from fastapi.testclient import TestClient

from src.main import create_app

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_dockerfile_exists_and_uses_multistage_build():
    """Verify Dockerfile exists and enforces a multi-stage build architecture."""
    dockerfile_path = PROJECT_ROOT / "Dockerfile"
    assert dockerfile_path.exists(), "Dockerfile must exist at project root."

    content = dockerfile_path.read_text(encoding="utf-8")

    # Multi-stage verification
    assert "AS builder" in content, "Dockerfile must define a builder stage."
    assert "AS runtime" in content, "Dockerfile must define a runtime stage."
    assert "COPY --from=builder" in content, "Runtime stage must copy artifacts from builder stage."


def test_dockerfile_security_and_non_root_user():
    """Verify Dockerfile enforces unprivileged non-root execution and secret hygiene."""
    content = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")

    # Non-root user verification
    assert "useradd" in content, "Dockerfile must create an unprivileged system user."
    assert "USER appuser" in content, "Dockerfile must switch to non-root USER appuser."

    # Environment hardening
    assert "PYTHONUNBUFFERED=1" in content, "Dockerfile must set PYTHONUNBUFFERED=1."
    assert "PYTHONDONTWRITEBYTECODE=1" in content, "Dockerfile must set PYTHONDONTWRITEBYTECODE=1."

    # Expose standard port
    assert "EXPOSE 8080" in content, "Dockerfile must expose port 8080."

    # Container healthcheck
    assert "HEALTHCHECK" in content, "Dockerfile must declare a HEALTHCHECK instruction."
    assert "/health" in content, "Container HEALTHCHECK must target /health endpoint."


def test_dockerignore_security_exclusions():
    """Verify .dockerignore excludes sensitive files, virtualenvs, and secrets."""
    dockerignore_path = PROJECT_ROOT / ".dockerignore"
    assert dockerignore_path.exists(), ".dockerignore must exist at project root."

    content = dockerignore_path.read_text(encoding="utf-8")
    lines = [
        line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")
    ]

    # Crucial security exclusions
    assert ".venv/" in lines or ".venv" in lines, ".dockerignore must exclude .venv/."
    assert ".git/" in lines or ".git" in lines, ".dockerignore must exclude .git/."
    assert ".env" in lines, ".dockerignore must exclude .env secrets."
    assert "__pycache__/" in lines or "__pycache__" in lines, (
        ".dockerignore must exclude __pycache__."
    )


def test_docker_compose_configuration():
    """Verify docker-compose.yml defines the local container service correctly."""
    compose_path = PROJECT_ROOT / "docker-compose.yml"
    assert compose_path.exists(), "docker-compose.yml must exist at project root."

    content = compose_path.read_text(encoding="utf-8")

    assert "services:" in content
    assert "app:" in content
    assert "8080:8080" in content
    assert "healthcheck:" in content
    assert "/health" in content


def test_container_healthcheck_endpoint():
    """Verify FastAPI /health endpoint responds with 200 OK and healthy status for container probes."""
    app = create_app()
    client = TestClient(app)

    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "daily-hadith-ai-agent"
    assert "timezone" in data
    assert "scheduler" in data
