"""
Typed Workflow State Schema for the Daily Hadith Delivery StateGraph.

Defines the durable state dictionary that flows through all execution nodes,
tracking candidate provenance, deterministic verification, AI reflection status,
and delivery idempotency.
"""

import zoneinfo
from datetime import date, datetime
from typing import TypedDict

from src.config import get_settings


class DailyWorkflowState(TypedDict, total=False):
    """
    State schema for the Daily Hadith LangGraph pipeline.
    """

    # Target Calendar Scheduling
    scheduled_date: str  # YYYY-MM-DD
    is_idempotent: bool  # True if a successful delivery already occurred for this date

    # Selected Hadith Candidate Data
    candidate_id: int | None
    source_id: str | None
    collection: str | None
    hadith_number: str | None
    english_title: str | None
    english_text: str | None
    arabic_text: str | None
    attribution: str | None
    grade: str | None
    source_url: str | None

    # Deterministic Safety Gate
    verification_passed: bool

    # AI Commentary / Reflection (Segregated)
    ai_reflection: str | None
    ai_reflection_status: str  # "NOT_GENERATED" | "GENERATED" | "OMITTED" | "FAILED"

    # Notification Formatting & Multi-User Dispatch
    formatted_message: str | None
    telegram_message_id: int | None
    subscribers_count: int | None
    delivered_count: int | None
    failed_count: int | None

    # Execution Lifecycle & Auditing
    # "PENDING" | "COMPLETED" | "SKIPPED_IDEMPOTENT" | "ABORTED_NO_CANDIDATE" | "ABORTED_VALIDATION_FAILED" | "FAILED"
    status: str
    error_message: str | None


def get_current_ist_date() -> str:
    """Return the current calendar date in Asia/Kolkata timezone as YYYY-MM-DD."""
    settings = get_settings()
    tz = zoneinfo.ZoneInfo(settings.timezone)
    return datetime.now(tz).date().isoformat()


def create_initial_state(
    scheduled_date: str | date | None = None,
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
