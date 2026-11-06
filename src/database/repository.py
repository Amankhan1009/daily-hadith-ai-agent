"""
Database Repository Layer.

Encapsulates CRUD operations, candidate deduplication, and daily delivery
idempotency queries.
"""

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.models import DailyDeliveryLog, HadithCandidate


def get_candidate_by_source_id(session: Session, source_id: str) -> Optional[HadithCandidate]:
    """Retrieve a Hadith candidate by its HadeethEnc record ID."""
    stmt = select(HadithCandidate).where(HadithCandidate.source_id == str(source_id))
    return session.scalars(stmt).first()


def save_candidate(
    session: Session,
    source_id: str,
    collection: str,
    english_title: str,
    english_text: str,
    arabic_text: str,
    attribution: str,
    grade: str,
    source_url: str,
    hadith_number: Optional[str] = None,
    translation_version: Optional[str] = None,
    verification_status: str = "PENDING",
    rejection_reason: Optional[str] = None,
) -> HadithCandidate:
    """Create or update a Hadith candidate record."""
    candidate = get_candidate_by_source_id(session, source_id)
    if candidate is None:
        candidate = HadithCandidate(
            source_id=str(source_id),
            collection=collection,
            hadith_number=hadith_number,
            english_title=english_title,
            english_text=english_text,
            arabic_text=arabic_text,
            attribution=attribution,
            grade=grade,
            source_url=source_url,
            translation_version=translation_version,
            verification_status=verification_status,
            rejection_reason=rejection_reason,
        )
        session.add(candidate)
    else:
        candidate.collection = collection
        candidate.hadith_number = hadith_number
        candidate.english_title = english_title
        candidate.english_text = english_text
        candidate.arabic_text = arabic_text
        candidate.attribution = attribution
        candidate.grade = grade
        candidate.source_url = source_url
        candidate.translation_version = translation_version
        candidate.verification_status = verification_status
        candidate.rejection_reason = rejection_reason

    session.flush()
    return candidate


def is_date_delivered(session: Session, scheduled_date: date) -> bool:
    """
    Check if a successful delivery already occurred on a given calendar date.
    Enforces daily idempotency.
    """
    stmt = (
        select(DailyDeliveryLog.id)
        .where(DailyDeliveryLog.scheduled_date == scheduled_date)
        .where(DailyDeliveryLog.status == "SUCCESS")
    )
    return session.scalars(stmt).first() is not None


# Convenience alias
is_delivery_recorded = is_date_delivered


def get_next_verified_candidate(session: Session) -> Optional[HadithCandidate]:
    """
    Find the earliest verified candidate that has not yet been delivered.
    """
    delivered_candidate_ids = (
        select(DailyDeliveryLog.candidate_id)
        .where(DailyDeliveryLog.status == "SUCCESS")
        .where(DailyDeliveryLog.candidate_id.is_not(None))
    )

    stmt = (
        select(HadithCandidate)
        .where(HadithCandidate.verification_status == "VERIFIED")
        .where(HadithCandidate.id.not_in(delivered_candidate_ids))
        .order_by(HadithCandidate.id.asc())
    )
    return session.scalars(stmt).first()


def record_delivery_log(
    session: Session,
    scheduled_date: date,
    status: str,
    candidate_id: Optional[int] = None,
    error_message: Optional[str] = None,
    telegram_message_id: Optional[int] = None,
) -> DailyDeliveryLog:
    """
    Create or update the delivery log for a calendar date.
    """
    stmt = select(DailyDeliveryLog).where(DailyDeliveryLog.scheduled_date == scheduled_date)
    log = session.scalars(stmt).first()

    now = datetime.now(timezone.utc)
    if log is None:
        log = DailyDeliveryLog(
            scheduled_date=scheduled_date,
            candidate_id=candidate_id,
            status=status,
            error_message=error_message,
            telegram_message_id=telegram_message_id,
            delivered_at=now if status == "SUCCESS" else None,
            attempt_count=1,
        )
        session.add(log)
    else:
        log.candidate_id = candidate_id or log.candidate_id
        log.status = status
        log.error_message = error_message
        log.telegram_message_id = telegram_message_id or log.telegram_message_id
        log.attempt_count += 1
        if status == "SUCCESS":
            log.delivered_at = now

    session.flush()
    return log