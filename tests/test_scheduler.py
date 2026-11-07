"""
Automated Unit and Contract Tests for Daily Runner, Scheduler, and FastAPI Endpoints.
"""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.database.models import HadithCandidate
from src.database.repository import get_or_create_subscriber, save_candidate
from src.database.session import Base
from src.main import create_app
from src.workflow.daily_runner import run_daily_broadcast
from src.workflow.scheduler import create_daily_scheduler


@pytest.fixture
def test_db_session() -> Generator[Session]:
    """Provides an isolated in-memory SQLite database session."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def seed_candidate(test_db_session: Session) -> HadithCandidate:
    """Seed verified candidate."""
    cand = save_candidate(
        session=test_db_session,
        source_id="5913",
        collection="Sahih al-Bukhari",
        hadith_number="5027",
        english_title="Learn Quran",
        english_text="The best among you learn the Quran.",
        arabic_text="خيركم من تعلم القرآن",
        attribution="Narrated by Al-Bukhari",
        grade="Authentic",
        source_url="https://hadeethenc.com/en/browse/hadith/5913",
        verification_status="VERIFIED",
    )
    test_db_session.commit()
    return cand


def test_daily_runner_dry_run_executes_cleanly(test_db_session, seed_candidate, monkeypatch):
    """Verify daily_runner in dry-run mode completes without calling external APIs."""
    get_or_create_subscriber(test_db_session, chat_id=123456)
    test_db_session.commit()

    with patch("src.workflow.nodes.get_db_session") as mock_get_session:
        mock_get_session.return_value.__enter__.return_value = test_db_session
        final_state = run_daily_broadcast(target_date="2026-11-25", dry_run=True)

    assert final_state["status"] == "COMPLETED"
    assert final_state["is_idempotent"] is False
    assert final_state["subscribers_count"] == 1
    assert final_state["delivered_count"] == 1


def test_scheduler_timezone_and_misfire_configuration():
    """Verify scheduler is configured for Asia/Kolkata at 10:00 AM with 3600s misfire grace time."""
    scheduler = create_daily_scheduler()
    job = scheduler.get_job("daily_hadith_broadcast")

    assert job is not None
    assert str(scheduler.timezone) == "Asia/Kolkata"
    assert job.misfire_grace_time == 3600
    assert job.coalesce is True


def test_api_health_endpoint():
    """Verify GET /health returns service status and timezone."""
    app = create_app()
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "daily-hadith-ai-agent"
    assert data["timezone"] == "Asia/Kolkata"


def test_api_cron_endpoint_security_and_dispatch(monkeypatch):
    """Verify POST /api/cron/daily-broadcast rejects invalid secret and accepts valid token."""
    monkeypatch.setenv("CRON_SECRET_TOKEN", "valid_cron_secret_777")
    from src.config import get_settings

    get_settings.cache_clear()

    app = create_app()
    client = TestClient(app)

    # 1. Missing secret token -> 403
    res_unauth = client.post("/api/cron/daily-broadcast")
    assert res_unauth.status_code == 403

    # 2. Invalid secret token -> 403
    res_wrong = client.post(
        "/api/cron/daily-broadcast",
        headers={"X-Cron-Secret": "wrong_token"},
    )
    assert res_wrong.status_code == 403

    # 3. Valid secret token via header -> triggers broadcast
    with patch("src.main.run_daily_broadcast") as mock_run:
        mock_run.return_value = {
            "status": "COMPLETED",
            "scheduled_date": "2026-11-25",
            "candidate_id": 10,
            "delivered_count": 5,
        }
        res_valid = client.post(
            "/api/cron/daily-broadcast",
            headers={"X-Cron-Secret": "valid_cron_secret_777"},
        )
        assert res_valid.status_code == 200
        assert res_valid.json()["ok"] is True
        assert res_valid.json()["delivered_count"] == 5

    get_settings.cache_clear()
