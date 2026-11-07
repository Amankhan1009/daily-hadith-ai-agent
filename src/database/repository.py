"""
Database Repository Layer.

Encapsulates CRUD operations, candidate deduplication, and daily delivery
idempotency queries.
"""

from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.models import (
    DailyDeliveryLog,
    HadithCandidate,
    SubscriberDeliveryLog,
    TelegramSubscriber,
)


def get_candidate_by_source_id(session: Session, source_id: str) -> HadithCandidate | None:
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
    hadith_number: str | None = None,
    translation_version: str | None = None,
    verification_status: str = "PENDING",
    rejection_reason: str | None = None,
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


def get_next_verified_candidate(session: Session) -> HadithCandidate | None:
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
    candidate_id: int | None = None,
    error_message: str | None = None,
    telegram_message_id: int | None = None,
) -> DailyDeliveryLog:
    """
    Create or update the delivery log for a calendar date.
    """
    stmt = select(DailyDeliveryLog).where(DailyDeliveryLog.scheduled_date == scheduled_date)
    log = session.scalars(stmt).first()

    now = datetime.now(UTC)
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


def get_subscriber_by_chat_id(session: Session, chat_id: int) -> TelegramSubscriber | None:
    """Retrieve a subscriber by their Telegram chat ID."""
    stmt = select(TelegramSubscriber).where(TelegramSubscriber.chat_id == chat_id)
    return session.scalars(stmt).first()


def get_or_create_subscriber(
    session: Session,
    chat_id: int,
    username: str | None = None,
    first_name: str | None = None,
) -> tuple[TelegramSubscriber, bool]:
    """
    Idempotently register or reactivate a subscriber.

    Returns:
        tuple[TelegramSubscriber, bool]: (subscriber, created)
        - created is True if a new record was inserted.
        - created is False if existing record was found or reactivated.
    """
    subscriber = get_subscriber_by_chat_id(session, chat_id)
    now = datetime.now(UTC)

    if subscriber is None:
        subscriber = TelegramSubscriber(
            chat_id=chat_id,
            username=username,
            first_name=first_name,
            is_active=True,
            joined_at=now,
            updated_at=now,
        )
        session.add(subscriber)
        session.flush()
        return subscriber, True

    # Reactivate if previously opted out or blocked
    needs_update = False
    if not subscriber.is_active:
        subscriber.is_active = True
        needs_update = True
    if username is not None and subscriber.username != username:
        subscriber.username = username
        needs_update = True
    if first_name is not None and subscriber.first_name != first_name:
        subscriber.first_name = first_name
        needs_update = True

    if needs_update:
        subscriber.updated_at = now
        session.flush()

    return subscriber, False


def deactivate_subscriber(session: Session, chat_id: int) -> bool:
    """
    Deactivate a subscriber by chat ID (opt-out via /stop or bot blocked).
    Returns True if an active subscriber was deactivated, False otherwise.
    """
    subscriber = get_subscriber_by_chat_id(session, chat_id)
    if subscriber is not None and subscriber.is_active:
        subscriber.is_active = False
        subscriber.updated_at = datetime.now(UTC)
        session.flush()
        return True
    return False


def get_active_subscribers(session: Session) -> list[TelegramSubscriber]:
    """Retrieve all active subscribers for daily broadcast dispatch."""
    stmt = (
        select(TelegramSubscriber)
        .where(TelegramSubscriber.is_active == True)  # noqa: E712
        .order_by(TelegramSubscriber.id.asc())
    )
    return list(session.scalars(stmt).all())


def get_undelivered_active_subscribers(
    session: Session, scheduled_date: date
) -> list[TelegramSubscriber]:
    """
    Retrieve active subscribers who have not yet received a successful delivery on scheduled_date.
    Guarantees mid-run recovery without sending duplicate notifications.
    """
    delivered_subscriber_ids = (
        select(SubscriberDeliveryLog.subscriber_id)
        .where(SubscriberDeliveryLog.scheduled_date == scheduled_date)
        .where(SubscriberDeliveryLog.status == "DELIVERED")
    )

    stmt = (
        select(TelegramSubscriber)
        .where(TelegramSubscriber.is_active == True)  # noqa: E712
        .where(TelegramSubscriber.id.not_in(delivered_subscriber_ids))
        .order_by(TelegramSubscriber.id.asc())
    )
    return list(session.scalars(stmt).all())


def record_subscriber_delivery(
    session: Session,
    subscriber_id: int,
    chat_id: int,
    scheduled_date: date,
    candidate_id: int | None,
    status: str,
    telegram_message_id: int | None = None,
    error_message: str | None = None,
) -> SubscriberDeliveryLog:
    """
    Record or update an individual subscriber's delivery status for a calendar date.
    """
    stmt = (
        select(SubscriberDeliveryLog)
        .where(SubscriberDeliveryLog.subscriber_id == subscriber_id)
        .where(SubscriberDeliveryLog.scheduled_date == scheduled_date)
    )
    log = session.scalars(stmt).first()
    now = datetime.now(UTC)

    if log is None:
        log = SubscriberDeliveryLog(
            subscriber_id=subscriber_id,
            chat_id=chat_id,
            scheduled_date=scheduled_date,
            candidate_id=candidate_id,
            status=status,
            telegram_message_id=telegram_message_id,
            error_message=error_message,
            delivered_at=now if status == "DELIVERED" else None,
        )
        session.add(log)
    else:
        log.status = status
        log.candidate_id = candidate_id or log.candidate_id
        log.telegram_message_id = telegram_message_id or log.telegram_message_id
        log.error_message = error_message
        if status == "DELIVERED":
            log.delivered_at = now

    session.flush()
    return log


def is_subscriber_delivered(session: Session, subscriber_id: int, scheduled_date: date) -> bool:
    """Check if a specific subscriber was already successfully delivered to on scheduled_date."""
    stmt = (
        select(SubscriberDeliveryLog.id)
        .where(SubscriberDeliveryLog.subscriber_id == subscriber_id)
        .where(SubscriberDeliveryLog.scheduled_date == scheduled_date)
        .where(SubscriberDeliveryLog.status == "DELIVERED")
    )
    return session.scalars(stmt).first() is not None
