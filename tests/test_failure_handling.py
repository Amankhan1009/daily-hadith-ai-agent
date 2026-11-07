"""
Failure Handling and Stress Testing Suite.

Validates fail-closed safety, error recovery, and resilience across:
1. HadeethEnc API failures (500s, timeouts, malformed JSON, partial batch failures).
2. Groq LLM degradation (omitted key, rate limits, API crashes, guardrail omission).
3. Telegram Bot API failures (transient retries, HTTP 403 auto-deactivation, rate limit 429 backoff).
4. Inbound Webhook edge cases (forged tokens, malformed JSON, non-message updates).
5. Neon/SQLite database constraints and rollback integrity.
"""

import time
from datetime import date
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.config import get_settings
from src.database.models import (
    Base,
    DailyDeliveryLog,
    HadithCandidate,
    SubscriberDeliveryLog,
    TelegramSubscriber,
)
from src.database.repository import (
    get_subscriber_by_chat_id,
    save_candidate,
)
from src.delivery.router import get_db, router
from src.delivery.telegram import (
    TelegramClient,
    TelegramDeliveryError,
)
from src.hadeethenc.client import (
    HadeethEncClient,
    HadeethEncNetworkError,
    HadeethEncResponseError,
)
from src.hadeethenc.schemas import (
    HadeethEncArabicDetail,
    HadeethEncCandidatePair,
    HadeethEncEnglishDetail,
    HadeethEncListItem,
    HadeethEncListResponse,
    HadeethEncPaginationMeta,
)
from src.ingestion.service import CandidateIngestionService
from src.llm.client import GroqReflectionClient
from src.workflow.nodes import WorkflowNodes
from src.workflow.state import DailyWorkflowState

# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def test_db_session():
    """Provides an isolated, in-memory SQLite database session for stress tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_client(test_db_session: Session):
    """Provides a FastAPI TestClient with database session overridden."""
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: test_db_session
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 1. HadeethEnc API Failure Handling & Fail-Closed Invariants
# ---------------------------------------------------------------------------


def test_hadeethenc_500_server_error_fails_closed():
    """Verify HadeethEnc HTTP 500/503 raises HadeethEncResponseError without data corruption."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    transport = httpx.MockTransport(handler)
    mock_http_client = httpx.Client(transport=transport)
    client = HadeethEncClient(client=mock_http_client)

    with pytest.raises(HadeethEncResponseError) as exc_info:
        client.get_english_hadith(12345)
    assert "HTTP 500" in str(exc_info.value)


def test_hadeethenc_network_timeout_fails_closed():
    """Verify network timeouts raise HadeethEncNetworkError cleanly."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("Connection timed out after 10.0s")

    transport = httpx.MockTransport(handler)
    mock_http_client = httpx.Client(transport=transport)
    client = HadeethEncClient(client=mock_http_client)

    with pytest.raises(HadeethEncNetworkError) as exc_info:
        client.get_english_hadith(12345)
    assert "timed out" in str(exc_info.value)


def test_hadeethenc_malformed_json_fails_closed():
    """Verify unparseable HTML/malformed JSON responses fail closed."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=b"<html>Bad Gateway</html>", headers={"content-type": "text/html"}
        )

    transport = httpx.MockTransport(handler)
    mock_http_client = httpx.Client(transport=transport)
    client = HadeethEncClient(client=mock_http_client)

    with pytest.raises(HadeethEncResponseError) as exc_info:
        client.get_english_hadith(12345)
    assert "Failed to decode JSON" in str(exc_info.value)


def test_ingestion_batch_survives_partial_api_outages(test_db_session: Session):
    """
    Verify that an API failure on record #2 does not crash the batch:
    records #1 and #3 succeed and are verified, failed_requests metric records the failure.
    """
    mock_client = MagicMock(spec=HadeethEncClient)
    mock_client.get_hadiths_by_category.return_value = HadeethEncListResponse(
        data=[
            HadeethEncListItem(id="101", title="Hadith 101", translations=["en", "ar"]),
            HadeethEncListItem(id="102", title="Hadith 102", translations=["en", "ar"]),
            HadeethEncListItem(id="103", title="Hadith 103", translations=["en", "ar"]),
        ],
        meta=HadeethEncPaginationMeta(current_page="1", last_page=1, total_items=3, per_page="20"),
    )

    pair101 = HadeethEncCandidatePair(
        source_id="101",
        english=HadeethEncEnglishDetail(
            id="101",
            title="Intentions",
            hadeeth="Actions are judged by intentions.",
            attribution="Narrated by Al-Bukhari",
            grade="Authentic",
            hadeeth_ar="«إنما الأعمال بالنيات»",
            attribution_ar="رواه البخاري",
            grade_ar="صحيح",
        ),
        arabic=HadeethEncArabicDetail(
            id="101",
            title="النيات",
            hadeeth="«إنما الأعمال بالنيات»",
            attribution="رواه البخاري",
            grade="صحيح",
            reference="صحيح البخاري (1)",
        ),
        canonical_url="https://hadeethenc.com/en/browse/hadith/101",
    )

    pair103 = HadeethEncCandidatePair(
        source_id="103",
        english=HadeethEncEnglishDetail(
            id="103",
            title="Faith",
            hadeeth="Faith has sixty branches.",
            attribution="Narrated by Muslim",
            grade="Authentic",
            hadeeth_ar="«الإيمان بضع وستون شعبة»",
            attribution_ar="رواه مسلم",
            grade_ar="صحيح",
        ),
        arabic=HadeethEncArabicDetail(
            id="103",
            title="الإيمان",
            hadeeth="«الإيمان بضع وستون شعبة»",
            attribution="رواه مسلم",
            grade="صحيح",
            reference="صحيح مسلم (35)",
        ),
        canonical_url="https://hadeethenc.com/en/browse/hadith/103",
    )

    def mock_get_pair(source_id: str):
        if str(source_id) == "101":
            return pair101
        if str(source_id) == "103":
            return pair103
        raise HadeethEncResponseError("HTTP 502: Bad Gateway")

    mock_client.get_candidate_pair.side_effect = mock_get_pair

    service = CandidateIngestionService(client=mock_client)
    summary = service.ingest_category_batch(session=test_db_session, category_id=5)

    assert summary.total_scanned == 3
    assert summary.newly_verified == 2
    assert summary.failed_requests == 1

    candidates = test_db_session.query(HadithCandidate).all()
    assert len(candidates) == 2
    assert {c.source_id for c in candidates} == {"101", "103"}


# ---------------------------------------------------------------------------
# 2. Groq LLM Degradation, Rate Limits & Guardrail Boundaries
# ---------------------------------------------------------------------------


def test_groq_missing_api_key_reflection_omitted():
    """Verify missing GROQ_API_KEY returns status OMITTED without raising exceptions."""
    client = GroqReflectionClient()
    client._client = None
    result = client.generate_reflection(
        english_text="Actions are by intentions.",
        attribution="Narrated by Al-Bukhari",
        collection="Sahih al-Bukhari",
    )
    assert result.status == "OMITTED"
    assert result.reflection is None


def test_groq_rate_limit_or_api_exception_fallback():
    """Verify Groq API exception (rate limit or connection drop) yields FAILED fallback."""

    class FailingGroqClient:
        @property
        def chat(self):
            raise RuntimeError("429 Too Many Requests: Rate limit reached")

    client = GroqReflectionClient(api_key="gsk_test")
    client._client = FailingGroqClient()

    result = client.generate_reflection(
        english_text="Actions are by intentions.",
        attribution="Narrated by Al-Bukhari",
        collection="Sahih al-Bukhari",
    )
    assert result.status == "FAILED"
    assert result.reflection is None


def test_groq_guardrail_violation_drops_reflection_safely(test_db_session: Session):
    """
    Verify that if the LLM produces a theological decree / fatwa, the guardrail
    gate drops the reflection, yet the authentic Hadith is delivered intact.
    """
    candidate = save_candidate(
        session=test_db_session,
        source_id="5907",
        collection="Sahih al-Bukhari",
        hadith_number="1",
        english_title="Intentions",
        english_text="Actions are according to intentions.",
        arabic_text="إنما الأعمال بالنيات",
        attribution="Sahih al-Bukhari (1)",
        grade="Sahih",
        source_url="https://hadeethenc.com/en/browse/hadith/5907",
        verification_status="VERIFIED",
    )
    test_db_session.commit()

    nodes = WorkflowNodes(session=test_db_session)

    state: DailyWorkflowState = {
        "scheduled_date": "2026-11-07",
        "is_idempotent": False,
        "candidate_id": candidate.id,
        "collection": candidate.collection,
        "hadith_number": candidate.hadith_number,
        "english_title": candidate.english_title,
        "english_text": candidate.english_text,
        "arabic_text": candidate.arabic_text,
        "attribution": candidate.attribution,
        "grade": candidate.grade,
        "source_url": candidate.source_url,
        "ai_reflection": "• The ruling is that this action is a binding fatwa under Islamic law.",
        "ai_reflection_status": "GENERATED",
        "formatted_message": None,
        "telegram_message_id": None,
        "delivered_count": 0,
        "subscribers_count": 0,
        "failed_count": 0,
        "error_message": None,
        "status": "PENDING",
    }

    # Run guardrails node
    guardrail_update = nodes.validate_guardrails_node(state)
    assert guardrail_update["ai_reflection_status"] == "OMITTED_GUARDRAIL_FAILED"
    assert guardrail_update["ai_reflection"] is None

    # Format message with omitted reflection
    state.update(guardrail_update)
    format_update = nodes.format_message_node(state)
    formatted = format_update["formatted_message"]

    # Canonical Hadith is present, theological decree is omitted
    assert "Actions are according to intentions." in formatted
    assert "binding fatwa" not in formatted


# ---------------------------------------------------------------------------
# 3. Telegram Bot API Delivery Resilience & Fan-Out Failure Isolation
# ---------------------------------------------------------------------------


def test_telegram_http_500_retries_and_succeeds(monkeypatch):
    """Verify Telegram 500 error triggers exponential backoff retry and succeeds on attempt 2."""
    monkeypatch.setattr(time, "sleep", lambda s: None)
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(500, json={"ok": False, "description": "Internal Server Error"})
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 888}})

    transport = httpx.MockTransport(handler)
    client = TelegramClient(bot_token="test_token", client=httpx.Client(transport=transport))

    result = client.send_message(chat_id=12345, text="Peace and blessings.")
    assert attempts == 2
    assert result.get("message_id") == 888


def test_telegram_http_500_retries_exhausted_raises_delivery_error(monkeypatch):
    """Verify persistent Telegram 500 errors exhaust retries and raise TelegramDeliveryError."""
    monkeypatch.setattr(time, "sleep", lambda s: None)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            500, json={"ok": False, "description": "Persistent Internal Server Error"}
        )

    transport = httpx.MockTransport(handler)
    client = TelegramClient(
        bot_token="test_token", max_retries=3, client=httpx.Client(transport=transport)
    )

    with pytest.raises(TelegramDeliveryError) as exc_info:
        client.send_message(chat_id=12345, text="Peace and blessings.")
    assert "Exhausted 3 attempts" in str(exc_info.value)


def test_telegram_message_overflow_fails_closed():
    """Verify messages > 4096 characters fail immediately before network dispatch."""
    client = TelegramClient(bot_token="test_token")
    oversized = "X" * 4097
    with pytest.raises(ValueError) as exc_info:
        client.send_message(chat_id=12345, text=oversized)
    assert "exceeds Telegram 4096-character limit" in str(exc_info.value)


def test_telegram_fanout_handles_mixed_subscriber_states(test_db_session: Session, monkeypatch):
    """
    Stress-test fan-out across 3 subscribers with mixed responses:
    - User 1: 200 OK (Delivered)
    - User 2: 403 Forbidden (Blocked -> auto-deactivated)
    - User 3: 500 Error (Transient network failure -> FAILED)
    Guarantees that User 2 or 3 failure does not abort delivery to User 1 or leave unrecorded logs.
    """
    monkeypatch.setattr(time, "sleep", lambda s: None)

    sub1 = TelegramSubscriber(chat_id=1001, username="user_one", is_active=True)
    sub2 = TelegramSubscriber(chat_id=1002, username="user_two", is_active=True)
    sub3 = TelegramSubscriber(chat_id=1003, username="user_three", is_active=True)
    test_db_session.add_all([sub1, sub2, sub3])

    candidate = save_candidate(
        session=test_db_session,
        source_id="5907",
        collection="Sahih al-Bukhari",
        hadith_number="1",
        english_title="Intentions",
        english_text="Actions are by intentions.",
        arabic_text="إنما الأعمال بالنيات",
        attribution="Sahih al-Bukhari (1)",
        grade="Sahih",
        source_url="https://hadeethenc.com/en/browse/hadith/5907",
        verification_status="VERIFIED",
    )
    test_db_session.commit()

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        body = json.loads(request.content.decode("utf-8"))
        chat_id = body.get("chat_id")
        if chat_id == 1001:
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 5001}})
        elif chat_id == 1002:
            return httpx.Response(
                403, json={"ok": False, "description": "Forbidden: bot was blocked by the user"}
            )
        elif chat_id == 1003:
            return httpx.Response(500, json={"ok": False, "description": "Server Error"})
        return httpx.Response(400)

    transport = httpx.MockTransport(handler)
    telegram_client = TelegramClient(
        bot_token="test_token", max_retries=1, client=httpx.Client(transport=transport)
    )

    nodes = WorkflowNodes(session=test_db_session, telegram_client=telegram_client)

    state: DailyWorkflowState = {
        "scheduled_date": "2026-11-07",
        "is_idempotent": False,
        "candidate_id": candidate.id,
        "hadith_record": None,
        "raw_reflection": None,
        "reflection_status": "OMITTED",
        "reflection": None,
        "guardrail_violations": [],
        "formatted_message": "Daily Hadith Notification",
        "telegram_message_id": None,
        "delivered_count": 0,
        "subscribers_count": 0,
        "failed_count": 0,
        "error_message": None,
        "status": "PENDING",
    }

    result = nodes.deliver_telegram_node(state)

    assert result["delivered_count"] == 1
    assert result["failed_count"] == 2
    assert result["subscribers_count"] == 3

    # Check subscriber 1002 was auto-deactivated
    sub2_reloaded = get_subscriber_by_chat_id(test_db_session, 1002)
    assert sub2_reloaded.is_active is False

    # Check subscriber 1001 and 1003 remain active
    sub1_reloaded = get_subscriber_by_chat_id(test_db_session, 1001)
    assert sub1_reloaded.is_active is True

    # Check delivery logs in database
    logs = (
        test_db_session.query(SubscriberDeliveryLog).order_by(SubscriberDeliveryLog.chat_id).all()
    )
    assert len(logs) == 3
    assert logs[0].status == "DELIVERED"
    assert logs[0].chat_id == 1001
    assert logs[1].status == "BLOCKED"
    assert logs[1].chat_id == 1002
    assert logs[2].status == "FAILED"
    assert logs[2].chat_id == 1003


# ---------------------------------------------------------------------------
# 4. Inbound Webhook Security & Payload Corruption Resilience
# ---------------------------------------------------------------------------


def test_webhook_forged_secret_token_returns_403(test_client: TestClient, monkeypatch):
    """Verify unauthorized or forged webhook calls receive HTTP 403 Forbidden."""
    monkeypatch.setattr(get_settings(), "telegram_webhook_secret", "super-secret-token")
    response = test_client.post(
        "/telegram/webhook",
        headers={"x-telegram-bot-api-secret-token": "attacker-forged-secret"},
        json={"update_id": 1},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Forbidden: Invalid secret token"


def test_webhook_missing_secret_token_returns_403(test_client: TestClient, monkeypatch):
    """Verify missing secret token header returns HTTP 403 Forbidden."""
    monkeypatch.setattr(get_settings(), "telegram_webhook_secret", "super-secret-token")
    response = test_client.post(
        "/telegram/webhook",
        json={"update_id": 1},
    )
    assert response.status_code == 403


def test_webhook_invalid_json_body_returns_gracefully(test_client: TestClient, monkeypatch):
    """Verify malformed non-JSON body returns graceful response without crashing the server."""
    monkeypatch.setattr(get_settings(), "telegram_webhook_secret", "")
    response = test_client.post(
        "/telegram/webhook",
        content=b"not-json{{{",
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 200
    assert response.json() == {"ok": False, "error": "Invalid JSON"}


def test_webhook_non_message_update_ignored(test_client: TestClient, monkeypatch):
    """Verify non-message updates (e.g., inline queries, reactions) are safely ignored with ok: true."""
    monkeypatch.setattr(get_settings(), "telegram_webhook_secret", "")
    response = test_client.post(
        "/telegram/webhook",
        json={"update_id": 9999, "inline_query": {"id": "query_1"}},
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_webhook_unrecognized_slash_command_gives_guidance(test_client: TestClient, monkeypatch):
    """Verify unrecognized slash command routes to guidance prompt."""
    monkeypatch.setattr(get_settings(), "telegram_webhook_secret", "")
    sent_messages = []

    def mock_send(self, chat_id, text, **kwargs):
        sent_messages.append({"chat_id": chat_id, "text": text})
        return {"message_id": 777}

    monkeypatch.setattr(TelegramClient, "send_message", mock_send)

    response = test_client.post(
        "/telegram/webhook",
        json={
            "update_id": 100,
            "message": {
                "chat": {"id": 88888},
                "from": {"id": 88888, "username": "inquirer"},
                "text": "/unknowncommand",
            },
        },
    )
    assert response.status_code == 200
    assert len(sent_messages) == 1
    assert "Unknown command" in sent_messages[0]["text"]


def test_webhook_unrecognized_text_acknowledged_silently(test_client: TestClient, monkeypatch):
    """Verify non-command plain text is acknowledged without noisy spam messages."""
    monkeypatch.setattr(get_settings(), "telegram_webhook_secret", "")
    sent_messages = []

    def mock_send(self, chat_id, text, **kwargs):
        sent_messages.append({"chat_id": chat_id, "text": text})
        return {"message_id": 777}

    monkeypatch.setattr(TelegramClient, "send_message", mock_send)

    response = test_client.post(
        "/telegram/webhook",
        json={
            "update_id": 101,
            "message": {
                "chat": {"id": 88888},
                "from": {"id": 88888, "username": "inquirer"},
                "text": "Hello bot, nice day!",
            },
        },
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert len(sent_messages) == 0


# ---------------------------------------------------------------------------
# 5. Database Constraint & Rollback Invariants
# ---------------------------------------------------------------------------


def test_daily_delivery_log_unique_date_constraint(test_db_session: Session):
    """Verify database unique constraint prevents duplicate daily delivery records."""
    target_date = date(2026, 11, 7)

    log1 = DailyDeliveryLog(scheduled_date=target_date, status="SUCCESS")
    test_db_session.add(log1)
    test_db_session.commit()

    log2 = DailyDeliveryLog(scheduled_date=target_date, status="SUCCESS")
    test_db_session.add(log2)

    # Second record on same date must raise IntegrityError
    with pytest.raises(IntegrityError):
        test_db_session.commit()
    test_db_session.rollback()


def test_subscriber_delivery_log_composite_unique_constraint(test_db_session: Session):
    """Verify composite unique constraint prevents duplicate subscriber delivery records."""
    target_date = date(2026, 11, 7)
    sub = TelegramSubscriber(chat_id=9999, username="test_user", is_active=True)
    test_db_session.add(sub)
    test_db_session.commit()

    log1 = SubscriberDeliveryLog(
        subscriber_id=sub.id,
        chat_id=sub.chat_id,
        scheduled_date=target_date,
        candidate_id=None,
        status="DELIVERED",
    )
    test_db_session.add(log1)
    test_db_session.commit()

    log2 = SubscriberDeliveryLog(
        subscriber_id=sub.id,
        chat_id=sub.chat_id,
        scheduled_date=target_date,
        candidate_id=None,
        status="DELIVERED",
    )
    test_db_session.add(log2)

    # Duplicate delivery record for same subscriber on same date must raise IntegrityError
    with pytest.raises(IntegrityError):
        test_db_session.commit()
    test_db_session.rollback()
