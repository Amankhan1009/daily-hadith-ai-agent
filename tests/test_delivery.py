"""
Automated Unit and Contract Tests for Outbound Telegram Client.
"""

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.database.session import Base
from src.delivery.router import get_db
from src.delivery.router import router as webhook_router
from src.delivery.telegram import (
    TelegramBotBlockedError,
    TelegramClient,
)


def test_send_message_success_mock():
    """Verify happy-path message delivery returns result payload."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/botTEST_TOKEN/sendMessage"
        return httpx.Response(
            200,
            json={"ok": True, "result": {"message_id": 9999, "text": "Test Hadith"}},
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = TelegramClient(bot_token="TEST_TOKEN", client=mock_client)

    result = client.send_message(chat_id=12345, text="Test Hadith")
    assert result["message_id"] == 9999


def test_send_message_exceeds_character_limit_raises_value_error():
    """Verify messages > 4096 characters fail-closed before network dispatch."""
    client = TelegramClient(bot_token="TEST_TOKEN")
    oversized_text = "A" * 4097

    with pytest.raises(ValueError, match="exceeds Telegram 4096-character limit"):
        client.send_message(chat_id=12345, text=oversized_text)


def test_send_message_403_raises_bot_blocked_error():
    """Verify HTTP 403 Forbidden raises TelegramBotBlockedError."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={
                "ok": False,
                "error_code": 403,
                "description": "Forbidden: bot was blocked by the user",
            },
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = TelegramClient(bot_token="TEST_TOKEN", client=mock_client)

    with pytest.raises(TelegramBotBlockedError) as exc_info:
        client.send_message(chat_id=12345, text="Hello")

    assert exc_info.value.chat_id == 12345
    assert "bot was blocked" in str(exc_info.value).lower()


def test_send_message_429_rate_limit_retry_succeeds():
    """Verify client handles HTTP 429 with retry_after and succeeds on subsequent attempt."""
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(
                429,
                json={"ok": False, "error_code": 429, "parameters": {"retry_after": 0.01}},
            )
        return httpx.Response(
            200,
            json={"ok": True, "result": {"message_id": 1001}},
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = TelegramClient(bot_token="TEST_TOKEN", client=mock_client)

    result = client.send_message(chat_id=12345, text="Rate limit test")
    assert calls == 2
    assert result["message_id"] == 1001


def test_webhook_management_helpers():
    """Verify set_webhook and delete_webhook endpoints."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/setWebhook"):
            return httpx.Response(200, json={"ok": True, "result": True})
        if request.url.path.endswith("/deleteWebhook"):
            return httpx.Response(200, json={"ok": True, "result": True})
        return httpx.Response(404)

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = TelegramClient(bot_token="TEST_TOKEN", client=mock_client)

    assert (
        client.set_webhook(url="https://example.com/telegram/webhook", secret_token="sec123")
        is True
    )
    assert client.delete_webhook() is True


@pytest.fixture
def test_db_session():
    """Provides an isolated in-memory SQLite database session for webhook tests."""
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
def api_client(test_db_session):
    app = FastAPI()
    app.include_router(webhook_router)
    app.dependency_overrides[get_db] = lambda: test_db_session
    return TestClient(app)


def test_webhook_rejects_missing_or_invalid_secret(api_client, monkeypatch):
    """Verify webhook rejects requests with invalid X-Telegram-Bot-Api-Secret-Token."""
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "super_secret_token_123")
    from src.config import get_settings

    get_settings.cache_clear()

    # Missing header -> 403
    response = api_client.post("/telegram/webhook", json={"update_id": 1})
    assert response.status_code == 403

    # Wrong header -> 403
    response = api_client.post(
        "/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong_token"},
        json={"update_id": 1},
    )
    assert response.status_code == 403

    # Correct header -> 200
    response = api_client.post(
        "/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "super_secret_token_123"},
        json={"update_id": 1},
    )
    assert response.status_code == 200
    get_settings.cache_clear()


def test_webhook_routes_start_command(api_client, monkeypatch):
    """Verify /start triggers subscriber registration and greeting."""
    sent_messages = []

    def mock_send_message(self, chat_id, text, **kwargs):
        sent_messages.append({"chat_id": chat_id, "text": text})
        return {"message_id": 101}

    monkeypatch.setattr(TelegramClient, "send_message", mock_send_message)

    payload = {
        "update_id": 100,
        "message": {
            "message_id": 1,
            "chat": {"id": 88888, "type": "private"},
            "from": {"id": 88888, "username": "newuser", "first_name": "New"},
            "text": "/start",
        },
    }

    response = api_client.post("/telegram/webhook", json=payload)
    assert response.status_code == 200
    assert len(sent_messages) >= 1
    assert "Assalamu Alaikum" in sent_messages[0]["text"]


def test_webhook_routes_stop_command(api_client, monkeypatch):
    """Verify /stop deactivates subscriber and confirms opt-out."""
    sent_messages = []

    def mock_send_message(self, chat_id, text, **kwargs):
        sent_messages.append({"chat_id": chat_id, "text": text})
        return {"message_id": 102}

    monkeypatch.setattr(TelegramClient, "send_message", mock_send_message)

    payload = {
        "update_id": 101,
        "message": {
            "message_id": 2,
            "chat": {"id": 88888, "type": "private"},
            "from": {"id": 88888, "username": "newuser"},
            "text": "/stop",
        },
    }

    response = api_client.post("/telegram/webhook", json=payload)
    assert response.status_code == 200
    assert any("unsubscribed" in msg["text"].lower() for msg in sent_messages)


def test_webhook_routes_help_command(api_client, monkeypatch):
    """Verify /help returns architectural guidance and command list."""
    sent_messages = []

    def mock_send_message(self, chat_id, text, **kwargs):
        sent_messages.append({"chat_id": chat_id, "text": text})
        return {"message_id": 103}

    monkeypatch.setattr(TelegramClient, "send_message", mock_send_message)

    payload = {
        "update_id": 102,
        "message": {
            "message_id": 3,
            "chat": {"id": 88888, "type": "private"},
            "from": {"id": 88888, "username": "newuser"},
            "text": "/help",
        },
    }

    response = api_client.post("/telegram/webhook", json=payload)
    assert response.status_code == 200
    assert any("Zero Text Modification" in msg["text"] for msg in sent_messages)
