"""
LangGraph Workflow Nodes.

Implements pure, testable node functions for checking idempotency, candidate
selection, deterministic safety validation, AI reflection generation, message
formatting, and delivery logging.
"""

from datetime import date
import logging
import time
from typing import Any, Optional
from sqlalchemy.orm import Session

from src.config import get_settings
from src.database.models import HadithCandidate
from src.database.repository import (
    deactivate_subscriber,
    get_active_subscribers,
    get_candidate_by_source_id,
    get_next_verified_candidate,
    get_undelivered_active_subscribers,
    is_date_delivered,
    record_delivery_log,
    record_subscriber_delivery,
)
from src.database.session import get_db_session
from src.delivery import TelegramBotBlockedError, TelegramClient
from src.formatter import format_daily_hadith_message
from src.guardrails import ReflectionValidator
from src.llm import GroqReflectionClient
from src.workflow.state import DailyWorkflowState

logger = logging.getLogger(__name__)

APPROVED_COLLECTIONS = {
    "Sahih al-Bukhari",
    "Sahih Muslim",
    "Agreed Upon (Al-Bukhari & Muslim)",
}


class WorkflowNodes:
    """
    Encapsulates all node functions of the Daily Hadith state graph.
    Allows injecting an explicit database session, LLM client, and validator
    or managing them dynamically via default providers.
    """

    def __init__(
        self,
        session: Optional[Session] = None,
        llm_client: Optional[GroqReflectionClient] = None,
        validator: Optional[ReflectionValidator] = None,
        telegram_client: Optional[TelegramClient] = None,
    ) -> None:
        self._session = session
        self._llm_client = llm_client or GroqReflectionClient()
        self._validator = validator or ReflectionValidator()
        self._telegram_client = telegram_client

    def check_idempotency_node(self, state: DailyWorkflowState) -> dict[str, Any]:
        """
        Node 1: Check if a delivery was already completed for the scheduled date.
        """
        scheduled_date_str = state.get("scheduled_date")
        target_date = (
            date.fromisoformat(scheduled_date_str)
            if scheduled_date_str
            else date.today()
        )

        def _execute(session: Session) -> dict[str, Any]:
            already_delivered = is_date_delivered(session, target_date)
            if already_delivered:
                return {
                    "is_idempotent": True,
                    "status": "SKIPPED_IDEMPOTENT",
                    "error_message": f"Delivery already completed for date {target_date.isoformat()}.",
                }
            return {
                "is_idempotent": False,
                "status": "PENDING",
                "error_message": None,
            }

        if self._session is not None:
            return _execute(self._session)
        with get_db_session() as session:
            return _execute(session)

    def fetch_candidate_node(self, state: DailyWorkflowState) -> dict[str, Any]:
        """
        Node 2: Select the next verified candidate from the database queue.
        """

        def _execute(session: Session) -> dict[str, Any]:
            candidate = get_next_verified_candidate(session)
            if candidate is None:
                return {
                    "status": "ABORTED_NO_CANDIDATE",
                    "error_message": "No verified candidates available in queue.",
                }

            return {
                "candidate_id": candidate.id,
                "source_id": candidate.source_id,
                "collection": candidate.collection,
                "hadith_number": candidate.hadith_number,
                "english_title": candidate.english_title,
                "english_text": candidate.english_text,
                "arabic_text": candidate.arabic_text,
                "attribution": candidate.attribution,
                "grade": candidate.grade,
                "source_url": candidate.source_url,
                "status": "PENDING",
            }

        if self._session is not None:
            return _execute(self._session)
        with get_db_session() as session:
            return _execute(session)

    def verify_safety_node(self, state: DailyWorkflowState) -> dict[str, Any]:
        """
        Node 3: Defense-in-depth safety gate ensuring candidate strictly complies
        with approved collection rules and canonical citations before dispatch.
        """
        collection = state.get("collection")
        hadith_number = state.get("hadith_number")
        english_text = state.get("english_text")
        arabic_text = state.get("arabic_text")

        # Invariant 1: Approved Collection Check
        if not collection or collection not in APPROVED_COLLECTIONS:
            return {
                "verification_passed": False,
                "status": "ABORTED_VALIDATION_FAILED",
                "error_message": f"Candidate cites unapproved collection: {collection}",
            }

        # Invariant 2: Mandatory Canonical Hadith Number
        if not hadith_number or str(hadith_number).strip().lower() in ("none", ""):
            return {
                "verification_passed": False,
                "status": "ABORTED_VALIDATION_FAILED",
                "error_message": "Candidate lacks a verified canonical Hadith number.",
            }

        # Invariant 3: Non-empty canonical text
        if not english_text or not arabic_text:
            return {
                "verification_passed": False,
                "status": "ABORTED_VALIDATION_FAILED",
                "error_message": "Candidate text payload is empty.",
            }

        return {
            "verification_passed": True,
            "status": "PENDING",
            "error_message": None,
        }

    def generate_reflection_node(self, state: DailyWorkflowState) -> dict[str, Any]:
        """
        Node 4: Generate segregated educational reflection using Groq LLM.
        Operates with fail-safe fallback (omits reflection if key is missing or API fails).
        """
        english_text = state.get("english_text", "")
        attribution = state.get("attribution", "")
        collection = state.get("collection", "")

        res = self._llm_client.generate_reflection(
            english_text=english_text,
            attribution=attribution,
            collection=collection,
        )

        return {
            "ai_reflection": res.reflection,
            "ai_reflection_status": res.status,
            "status": "PENDING",
        }

    def validate_guardrails_node(self, state: DailyWorkflowState) -> dict[str, Any]:
        """
        Node 5: Enforce Guardrails AI safety checks on generated reflection.
        If reflection violates theological boundaries, citations, or text leakage,
        safely omit the reflection while allowing the authentic Hadith to proceed.
        """
        reflection = state.get("ai_reflection")
        status = state.get("ai_reflection_status")

        if not reflection or status != "GENERATED":
            return {
                "ai_reflection": None,
                "ai_reflection_status": status,
                "status": "PENDING",
            }

        english_text = state.get("english_text", "")
        guard_res = self._validator.validate(
            reflection=reflection,
            source_hadith_text=english_text,
        )

        if not guard_res.is_valid:
            logger.warning(
                "Guardrail rejected AI reflection: [%s] %s. Omitting reflection fail-safe.",
                guard_res.error_code,
                guard_res.reason,
            )
            return {
                "ai_reflection": None,
                "ai_reflection_status": "OMITTED_GUARDRAIL_FAILED",
                "error_message": f"Guardrail: {guard_res.reason}",
                "status": "PENDING",
            }

        return {
            "ai_reflection": guard_res.sanitized_text or reflection,
            "ai_reflection_status": "PASSED_GUARDRAILS",
            "status": "PENDING",
        }

    def format_message_node(self, state: DailyWorkflowState) -> dict[str, Any]:
        """
        Node 6: Assemble the standardized notification message for Telegram using HTML formatting.
        """
        english_text = state.get("english_text", "").strip()
        attribution = state.get("attribution", "").strip()
        collection = state.get("collection", "").strip()
        hadith_number = str(state.get("hadith_number", "")).strip()
        grade = state.get("grade", "Authentic").strip()
        source_url = state.get("source_url", "").strip()
        ai_reflection = state.get("ai_reflection")
        reflection_status = state.get("ai_reflection_status")

        payload = format_daily_hadith_message(
            english_text=english_text,
            attribution=attribution,
            collection=collection,
            hadith_number=hadith_number,
            grade=grade,
            source_url=source_url,
            ai_reflection=ai_reflection,
            ai_reflection_status=reflection_status,
        )

        return {
            "formatted_message": payload.text,
            "status": "PENDING",
        }

    def deliver_telegram_node(self, state: DailyWorkflowState) -> dict[str, Any]:
        """
        Node 7: Fan out the formatted Hadith notification to all active, undelivered subscribers.
        Enforces:
        - Per-subscriber daily idempotency (skips users already delivered today)
        - 25 msg/sec rate-limiting throttle
        - Automatic deactivation and BLOCKED logging for HTTP 403 (bot blocked)
        - Individual commit per subscriber for mid-run crash recovery
        """
        formatted_message = state.get("formatted_message")
        if not formatted_message:
            return {
                "status": "FAILED",
                "error_message": "No formatted message available for delivery.",
            }

        scheduled_date_str = state.get("scheduled_date")
        target_date = (
            date.fromisoformat(scheduled_date_str)
            if scheduled_date_str
            else date.today()
        )
        candidate_id = state.get("candidate_id")

        client = self._telegram_client or TelegramClient()
        if not client.bot_token:
            logger.info("Telegram bot token not configured in dev/test mode. Skipping network dispatch.")
            return {
                "delivered_count": 0,
                "subscribers_count": 0,
                "status": "PENDING",
            }

        def _execute(session: Session) -> dict[str, Any]:
            # Query ONLY subscribers who have NOT yet received today's broadcast
            pending_subscribers = get_undelivered_active_subscribers(session, target_date)
            settings = get_settings()

            # Fallback if no subscribers in DB, but admin TELEGRAM_CHAT_ID is set
            if not pending_subscribers and not get_active_subscribers(session) and settings.telegram_chat_id:
                try:
                    fallback_id = int(settings.telegram_chat_id)
                except ValueError:
                    fallback_id = settings.telegram_chat_id

                try:
                    res = client.send_message(chat_id=fallback_id, text=formatted_message)
                    return {
                        "telegram_message_id": res.get("message_id") if isinstance(res, dict) else None,
                        "subscribers_count": 1,
                        "delivered_count": 1,
                        "failed_count": 0,
                        "status": "PENDING",
                    }
                except Exception as exc:
                    logger.error("Failed fallback delivery to admin chat %s: %s", fallback_id, exc)
                    return {
                        "subscribers_count": 1,
                        "delivered_count": 0,
                        "failed_count": 1,
                        "status": "PENDING",
                    }

            if not pending_subscribers:
                logger.info("All active subscribers already received daily delivery for date %s.", target_date)
                return {
                    "subscribers_count": 0,
                    "delivered_count": 0,
                    "failed_count": 0,
                    "status": "PENDING",
                }

            first_message_id = None
            delivered_count = 0
            failed_count = 0

            for sub in pending_subscribers:
                try:
                    res = client.send_message(chat_id=sub.chat_id, text=formatted_message)
                    msg_id = res.get("message_id") if isinstance(res, dict) else None
                    if first_message_id is None:
                        first_message_id = msg_id

                    # Record successful delivery immediately for crash recovery
                    record_subscriber_delivery(
                        session=session,
                        subscriber_id=sub.id,
                        chat_id=sub.chat_id,
                        scheduled_date=target_date,
                        candidate_id=candidate_id,
                        status="DELIVERED",
                        telegram_message_id=msg_id,
                    )
                    session.commit()
                    delivered_count += 1
                    time.sleep(0.04)  # 25 msgs/sec compliance

                except TelegramBotBlockedError:
                    logger.info("Subscriber %s blocked the bot. Deactivating...", sub.chat_id)
                    deactivate_subscriber(session, sub.chat_id)
                    record_subscriber_delivery(
                        session=session,
                        subscriber_id=sub.id,
                        chat_id=sub.chat_id,
                        scheduled_date=target_date,
                        candidate_id=candidate_id,
                        status="BLOCKED",
                        error_message="Forbidden: bot was blocked by the user",
                    )
                    session.commit()
                    failed_count += 1

                except Exception as exc:
                    logger.error("Failed to deliver daily Hadith to chat %s: %s", sub.chat_id, exc)
                    record_subscriber_delivery(
                        session=session,
                        subscriber_id=sub.id,
                        chat_id=sub.chat_id,
                        scheduled_date=target_date,
                        candidate_id=candidate_id,
                        status="FAILED",
                        error_message=str(exc),
                    )
                    session.commit()
                    failed_count += 1

            return {
                "telegram_message_id": first_message_id,
                "subscribers_count": len(pending_subscribers),
                "delivered_count": delivered_count,
                "failed_count": failed_count,
                "status": "PENDING",
            }

        if self._session is not None:
            return _execute(self._session)
        with get_db_session() as session:
            return _execute(session)


    def record_delivery_node(self, state: DailyWorkflowState) -> dict[str, Any]:
        """
        Node 6: Record the delivery outcome in DailyDeliveryLog for idempotency.
        """
        scheduled_date_str = state.get("scheduled_date")
        target_date = (
            date.fromisoformat(scheduled_date_str)
            if scheduled_date_str
            else date.today()
        )
        candidate_id = state.get("candidate_id")
        telegram_message_id = state.get("telegram_message_id")

        def _execute(session: Session) -> dict[str, Any]:
            record_delivery_log(
                session=session,
                scheduled_date=target_date,
                status="SUCCESS",
                candidate_id=candidate_id,
                telegram_message_id=telegram_message_id,
            )
            session.commit()
            return {
                "status": "COMPLETED",
                "error_message": None,
            }

        if self._session is not None:
            return _execute(self._session)
        with get_db_session() as session:
            return _execute(session)