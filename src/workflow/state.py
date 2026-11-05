"""
Typed Workflow State Schema for the Daily Hadith Delivery StateGraph.

Defines the durable state dictionary that flows through all execution nodes,
tracking candidate provenance, deterministic verification, AI reflection status,
and delivery idempotency.
"""

from datetime import date, datetime
from typing import Optional, TypedDict
import zoneinfo

from src.config import get_settings


class DailyWorkflowState(TypedDict, total=False):
    """
    State schema for the Daily Hadith LangGraph pipeline.
    """

    # Target Calendar Scheduling
    scheduled_date: str  # YYYY-MM-DD
    is_idempotent: bool  # True if a successful delivery already occurred for this date

    # Selected Hadith Candidate Data
    candidate_id: Optional[int]
    source_id: Optional[str]
    collection: Optional[str]
    hadith_number: Optional[str]
    english_title: Optional[str]
    english_text: Optional[str]
    arabic_text: Optional[str]
    attribution: Optional[str]
    grade: Optional[str]
    source_url: Optional[str]

    # Deterministic Safety Gate
    verification_passed: bool

    # AI Commentary / Reflection (Segregated)
    ai_reflection: Optional[str]
    ai_reflection_status: str  # "NOT_GENERATED" | "GENERATED" | "OMITTED" | "FAILED"

    # Notification Formatting & Dispatch
    formatted_message: Optional[str]
    telegram_message_id: Optional[int]

    # Execution Lifecycle & Auditing
    # "PENDING" | "COMPLETED" | "SKIPPED_IDEMPOTENT" | "ABORTED_NO_CANDIDATE" | "ABORTED_VALIDATION_FAILED" | "FAILED"
    status: str
    error_message: Optional[str]


def get_current_ist_date() -> str:
    """Return the current calendar date in Asia/Kolkata timezone as YYYY-MM-DD."""
    settings = get_settings()
    tz = zoneinfo.ZoneInfo(settings.app_timezone)
    return datetime.now(tz).date().isoformat()


def create_initial_state(
    scheduled_date: Optional[str | date] = None,
) -> DailyWorkflowState:
    """
    Construct a clean initial state dictionary for a daily pipeline run.
    """
    if scheduled_date is None:
        target_date_str = get_current_ist_date()
    elif isinstance(scheduled_date, date):
        target_date_str = scheduled_date.isoformat()
    else:
        target_date_str = str(scheduled_date)

    return DailyWorkflowState(
        scheduled_date=target_date_str,
        is_idempotent=False,
        candidate_id=None,
        source_id=None,
        collection=None,
        hadith_number=None,
        english_title=None,
        english_text=None,
        arabic_text=None,
        attribution=None,
        grade=None,
        source_url=None,
        verification_passed=False,
        ai_reflection=None,
        ai_reflection_status="NOT_GENERATED",
        formatted_message=None,
        telegram_message_id=None,
        status="PENDING",
        error_message=None,
    )