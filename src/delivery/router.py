"""
Inbound Telegram Webhook Router and Public Command Handlers.

Mounts POST /telegram/webhook, verifies X-Telegram-Bot-Api-Secret-Token,
and routes commands (/start, /today, /stop, /help).
"""

import hmac
import logging
from collections.abc import Generator
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from src.config import get_settings
from src.database.repository import (
    deactivate_subscriber,
    get_next_verified_candidate,
    get_or_create_subscriber,
)
from src.database.session import get_db_session
from src.delivery.telegram import TelegramBotBlockedError, TelegramClient
from src.formatter import format_daily_hadith_message

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telegram", tags=["Telegram Webhook"])


def get_db() -> Generator[Session]:
    """FastAPI dependency yielding a transactional database session."""
    with get_db_session() as session:
        yield session


def verify_webhook_secret(secret_token_header: str | None) -> bool:
    """
    Verify incoming X-Telegram-Bot-Api-Secret-Token using constant-time comparison.
    """
    configured_secret = get_settings().telegram_webhook_secret
    if not configured_secret:
        # Dev/testing mode if no secret configured
        return True

    if not secret_token_header:
        return False

    return hmac.compare_digest(secret_token_header, configured_secret)


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(None),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Receive and process inbound Telegram webhook updates.
    """
    if not verify_webhook_secret(x_telegram_bot_api_secret_token):
        logger.warning(
            "Rejected unauthorized Telegram webhook call: invalid or missing secret token."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Invalid secret token",
        )

    try:
        update: dict[str, Any] = await request.json()
    except Exception as exc:
        logger.error("Failed to parse JSON from Telegram webhook: %s", exc)
        return {"ok": False, "error": "Invalid JSON"}

    message = update.get("message") or update.get("edited_message")
    if not message:
        # Ignore non-message updates (e.g. status reactions, inline queries)
        return {"ok": True}

    chat = message.get("chat", {})
    chat_id = chat.get("id")
    if not chat_id:
        return {"ok": True}

    from_user = message.get("from", {})
    username = from_user.get("username")
    first_name = from_user.get("first_name")
    raw_text = (message.get("text") or "").strip()

    if not raw_text.startswith("/"):
        # Not a command; provide helpful hint
        return handle_unrecognized_text(chat_id)

    # Normalize command name (e.g. "/start@DailyHadithAiBot" -> "/start")
    command = raw_text.split()[0].lower().split("@")[0]

    telegram_client = TelegramClient()
    if command == "/start":
        return handle_start_command(session, telegram_client, chat_id, username, first_name)
    elif command in ("/today", "/hadith"):
        return handle_today_command(session, telegram_client, chat_id)
    elif command in ("/stop", "/unsubscribe"):
        return handle_stop_command(session, telegram_client, chat_id)
    elif command == "/help":
        return handle_help_command(telegram_client, chat_id)
    else:
        return handle_unknown_command(telegram_client, chat_id)


def handle_start_command(
    session: Session,
    client: TelegramClient,
    chat_id: int,
    username: str | None,
    first_name: str | None,
) -> dict[str, Any]:
    """Handle /start: Idempotently register subscriber and send today's Hadith."""
    subscriber, created = get_or_create_subscriber(
        session=session,
        chat_id=chat_id,
        username=username,
        first_name=first_name,
    )
    session.commit()

    greeting_name = f", {first_name}" if first_name else ""
    welcome_text = (
        f"<b>Assalamu Alaikum{greeting_name}! Welcome to the Daily Hadith AI Agent.</b>\n\n"
        "You are now subscribed to receive one authentic, verified Hadith every day at "
        "<b>10:00 AM (Asia/Kolkata)</b>.\n\n"
        "<b>Available Commands:</b>\n"
        "• /today — Read today's verified Hadith right now\n"
        "• /help — Inspect provenance, sources, and verification rules\n"
        "• /stop — Unsubscribe from daily deliveries anytime\n\n"
        "<i>Delivering today's Hadith to your chat below...</i>"
    )

    try:
        client.send_message(chat_id=chat_id, text=welcome_text)
    except TelegramBotBlockedError:
        deactivate_subscriber(session, chat_id)
        session.commit()
        return {"ok": False, "reason": "blocked"}

    # Also dispatch today's Hadith immediately for instant value
    return handle_today_command(session, client, chat_id)


def handle_today_command(session: Session, client: TelegramClient, chat_id: int) -> dict[str, Any]:
    """Handle /today: Fetch and send the current verified Hadith."""
    candidate = get_next_verified_candidate(session)
    if candidate is None:
        fallback_msg = (
            "<b>No Hadith available at this moment.</b>\n\n"
            "Our automated verification pipeline runs continuously. Please check back shortly!"
        )
        try:
            client.send_message(chat_id=chat_id, text=fallback_msg)
        except Exception:
            pass
        return {"ok": True}

    payload = format_daily_hadith_message(
        english_text=candidate.english_text,
        attribution=candidate.attribution,
        collection=candidate.collection,
        hadith_number=candidate.hadith_number or "",
        grade=candidate.grade,
        source_url=candidate.source_url,
        ai_reflection=candidate.ai_reflection,
        ai_reflection_status=candidate.ai_reflection_status,
    )

    try:
        client.send_message(chat_id=chat_id, text=payload.text)
    except TelegramBotBlockedError:
        deactivate_subscriber(session, chat_id)
        session.commit()
        return {"ok": False, "reason": "blocked"}
    except Exception as exc:
        logger.error("Failed to deliver /today Hadith to %s: %s", chat_id, exc)

    return {"ok": True}


def handle_stop_command(session: Session, client: TelegramClient, chat_id: int) -> dict[str, Any]:
    """Handle /stop: Gracefully opt out subscriber."""
    deactivate_subscriber(session, chat_id=chat_id)
    session.commit()

    goodbye_text = (
        "<b>You have been unsubscribed.</b>\n\n"
        "You will no longer receive daily Hadith notifications.\n"
        "If you ever wish to resume, simply send /start anytime."
    )
    try:
        client.send_message(chat_id=chat_id, text=goodbye_text)
    except Exception:
        pass

    return {"ok": True}


def handle_help_command(client: TelegramClient, chat_id: int) -> dict[str, Any]:
    """Handle /help: Display commands and architectural provenance safeguards."""
    help_text = (
        "<b>Daily Hadith AI Agent — Bot Guide</b>\n\n"
        "<b>Commands:</b>\n"
        "• /today — Read today's verified Hadith\n"
        "• /start — Subscribe or reactivate daily broadcasts (10:00 AM IST)\n"
        "• /stop — Unsubscribe from daily broadcasts\n"
        "• /help — View this guidance\n\n"
        "<b>Reliability & Theological Safeguards:</b>\n"
        "• <b>Zero Text Modification:</b> Sacred translations are retrieved directly from HadeethEnc and never altered or paraphrased.\n"
        "• <b>Deterministic Verification:</b> Citations are verified against Sahih al-Bukhari and Sahih Muslim references.\n"
        "• <b>Segregated Reflections:</b> Any AI reflections are strictly non-canonical commentary and clearly labeled."
    )
    try:
        client.send_message(chat_id=chat_id, text=help_text)
    except Exception:
        pass
    return {"ok": True}


def handle_unknown_command(client: TelegramClient, chat_id: int) -> dict[str, Any]:
    """Handle unrecognized slash command."""
    text = "Unknown command. Type /today to read today's Hadith, or /help for guidance."
    try:
        client.send_message(chat_id=chat_id, text=text)
    except Exception:
        pass
    return {"ok": True}


def handle_unrecognized_text(chat_id: int) -> dict[str, Any]:
    """Acknowledge non-command text without noisy errors."""
    return {"ok": True}
