"""
LangGraph Workflow Nodes.

Implements pure, testable node functions for checking idempotency, candidate
selection, deterministic safety validation, message formatting, and delivery logging.
"""

from datetime import date
from typing import Any, Optional
from sqlalchemy.orm import Session

from src.database.models import HadithCandidate
from src.database.repository import (
    get_candidate_by_source_id,
    get_next_verified_candidate,
    is_date_delivered,
    record_delivery_log,
)
from src.database.session import get_db_session
from src.workflow.state import DailyWorkflowState

APPROVED_COLLECTIONS = {
    "Sahih al-Bukhari",
    "Sahih Muslim",
    "Agreed Upon (Al-Bukhari & Muslim)",
}


class WorkflowNodes:
    """
    Encapsulates all node functions of the Daily Hadith state graph.
    Allows injecting an explicit database session (e.g. in tests) or managing
    sessions dynamically via get_db_session().
    """

    def __init__(self, session: Optional[Session] = None) -> None:
        self._session = session

    def _get_active_session(self) -> Session:
        """Return the active or current session."""
        if self._session is not None:
            return self._session
        raise RuntimeError("No database session provided.")

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

    def format_message_node(self, state: DailyWorkflowState) -> dict[str, Any]:
        """
        Node 4: Assemble the standardized notification message for Telegram.
        """
        english_text = state.get("english_text", "").strip()
        attribution = state.get("attribution", "").strip()
        collection = state.get("collection", "").strip()
        hadith_number = state.get("hadith_number", "").strip()
        grade = state.get("grade", "Authentic").strip()
        source_url = state.get("source_url", "").strip()
        ai_reflection = state.get("ai_reflection")

        message_parts = [
            "📖 *Hadith of the Day*",
            "",
            f'"{english_text}"',
            "",
            f"— *{attribution}*",
            f"📚 *Collection:* {collection} (#{hadith_number})",
            f"🏅 *Grade:* {grade}",
            "",
            f"🔗 *Canonical Source:* {source_url}",
        ]

        if ai_reflection and state.get("ai_reflection_status") == "GENERATED":
            message_parts.extend([
                "",
                "💡 *Reflection & Context:*",
                ai_reflection.strip(),
            ])

        formatted = "\n".join(message_parts)
        return {
            "formatted_message": formatted,
            "status": "PENDING",
        }

    def record_delivery_node(self, state: DailyWorkflowState) -> dict[str, Any]:
        """
        Node 5: Record the delivery outcome in DailyDeliveryLog for idempotency.
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