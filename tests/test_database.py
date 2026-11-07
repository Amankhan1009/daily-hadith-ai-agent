"""
Automated Unit Tests for Database Repositories and Idempotency Invariants.
"""

from collections.abc import Generator
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from src.database.models import DailyDeliveryLog
from src.database.repository import (
    deactivate_subscriber,
    get_active_subscribers,
    get_candidate_by_source_id,
    get_next_verified_candidate,
    get_or_create_subscriber,
    get_subscriber_by_chat_id,
    is_date_delivered,
    record_delivery_log,
    save_candidate,
)
from src.database.session import Base


@pytest.fixture
def db_session() -> Generator[Session]:
    """
    Provides an isolated in-memory SQLite database session for unit tests.
    Ensures zero pollution of cloud database and instant sub-second execution.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def test_save_and_retrieve_candidate(db_session: Session):
    """Verify storing a new Hadith candidate and looking it up by source_id."""
    candidate = save_candidate(
        session=db_session,
        source_id="5913",
        collection="Sahih al-Bukhari",
        hadith_number="5027",
        english_title="The best of you are those who learn the Qur'an and teach it",
        english_text="The Prophet said: The best among you are those who learn the Qur'an and teach it.",
        arabic_text="خيركم من تعلم القرآن وعلمه",
        attribution="Narrated by Al-Bukhari",
        grade="Authentic",
        source_url="https://hadeethenc.com/en/browse/hadith/5913",
        verification_status="VERIFIED",
    )
    db_session.commit()

    assert candidate.id is not None
    retrieved = get_candidate_by_source_id(db_session, "5913")
    assert retrieved is not None
    assert retrieved.collection == "Sahih al-Bukhari"
    assert retrieved.hadith_number == "5027"
    assert retrieved.verification_status == "VERIFIED"


def test_update_existing_candidate(db_session: Session):
    """Verify updating fields of an existing candidate preserves source_id identity."""
    save_candidate(
        session=db_session,
        source_id="5907",
        collection="Sahih Muslim",
        english_title="Initial Title",
        english_text="Initial text",
        arabic_text="نص أولي",
        attribution="Agreed upon",
        grade="Authentic",
        source_url="https://hadeethenc.com/en/browse/hadith/5907",
        verification_status="PENDING",
    )
    db_session.commit()

    # Update the candidate with verified details
    updated = save_candidate(
        session=db_session,
        source_id="5907",
        collection="Sahih Muslim",
        hadith_number="791",
        english_title="Updated Title",
        english_text="Updated text",
        arabic_text="نص محدث",
        attribution="Agreed upon",
        grade="Authentic",
        source_url="https://hadeethenc.com/en/browse/hadith/5907",
        verification_status="VERIFIED",
    )
    db_session.commit()

    assert updated.hadith_number == "791"
    assert updated.verification_status == "VERIFIED"


def test_idempotency_lifecycle(db_session: Session):
    """
    Test the core idempotency invariant:
    1. is_date_delivered is False before delivery.
    2. is_date_delivered is False if delivery fails.
    3. is_date_delivered becomes True only upon successful delivery.
    """
    today = date.today()

    # 1. Before delivery attempt
    assert is_date_delivered(db_session, today) is False

    # 2. Failed attempt should not lock the date
    record_delivery_log(
        session=db_session,
        scheduled_date=today,
        status="FAILED",
        error_message="Telegram API timeout",
    )
    db_session.commit()
    assert is_date_delivered(db_session, today) is False

    # 3. Successful delivery locks the date
    record_delivery_log(
        session=db_session,
        scheduled_date=today,
        status="SUCCESS",
        telegram_message_id=998877,
    )
    db_session.commit()
    assert is_date_delivered(db_session, today) is True


def test_get_next_verified_candidate_skips_delivered(db_session: Session):
    """
    Verify get_next_verified_candidate returns the next un-delivered verified Hadith
    and ignores unverified or already dispatched records.
    """
    c1 = save_candidate(
        session=db_session,
        source_id="101",
        collection="Sahih al-Bukhari",
        english_title="H1",
        english_text="Text 1",
        arabic_text="Arabic 1",
        attribution="Bukhari",
        grade="Sahih",
        source_url="url1",
        verification_status="VERIFIED",
    )
    c2 = save_candidate(
        session=db_session,
        source_id="102",
        collection="Sahih Muslim",
        english_title="H2",
        english_text="Text 2",
        arabic_text="Arabic 2",
        attribution="Muslim",
        grade="Sahih",
        source_url="url2",
        verification_status="VERIFIED",
    )
    # c3 is pending (unverified)
    save_candidate(
        session=db_session,
        source_id="103",
        collection="Sahih al-Bukhari",
        english_title="H3",
        english_text="Text 3",
        arabic_text="Arabic 3",
        attribution="Bukhari",
        grade="Sahih",
        source_url="url3",
        verification_status="PENDING",
    )
    db_session.commit()

    # Earliest verified is c1
    next_candidate = get_next_verified_candidate(db_session)
    assert next_candidate is not None
    assert next_candidate.id == c1.id

    # Mark c1 as delivered today
    record_delivery_log(
        session=db_session,
        scheduled_date=date.today(),
        status="SUCCESS",
        candidate_id=c1.id,
    )
    db_session.commit()

    # Next candidate should now be c2 (c3 is skipped because PENDING)
    next_candidate = get_next_verified_candidate(db_session)
    assert next_candidate is not None
    assert next_candidate.id == c2.id


def test_unique_constraint_on_scheduled_date(db_session: Session):
    """
    Verify the database raises an IntegrityError if attempting to insert
    two distinct delivery rows for the exact same calendar date.
    """
    target_date = date(2026, 11, 1)

    log1 = DailyDeliveryLog(scheduled_date=target_date, status="SUCCESS")
    db_session.add(log1)
    db_session.commit()

    # Attempting to insert a duplicate date directly violates the UNIQUE constraint
    log2 = DailyDeliveryLog(scheduled_date=target_date, status="FAILED")
    db_session.add(log2)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_get_or_create_subscriber_lifecycle(db_session: Session):
    """Verify creating a new subscriber and looking them up."""
    sub, created = get_or_create_subscriber(
        session=db_session,
        chat_id=987654321,
        username="aman_test",
        first_name="Aman",
    )
    db_session.commit()

    assert created is True
    assert sub.id is not None
    assert sub.chat_id == 987654321
    assert sub.username == "aman_test"
    assert sub.first_name == "Aman"
    assert sub.is_active is True

    # Duplicate /start: returns existing, created is False, no duplicate row
    sub2, created2 = get_or_create_subscriber(
        session=db_session,
        chat_id=987654321,
        username="aman_updated",
        first_name="Aman New",
    )
    db_session.commit()

    assert created2 is False
    assert sub2.id == sub.id
    assert sub2.username == "aman_updated"
    assert sub2.first_name == "Aman New"
    assert sub2.is_active is True


def test_deactivate_and_reactivate_subscriber(db_session: Session):
    """Verify opting out via deactivate_subscriber and reactivating via get_or_create_subscriber."""
    sub, _ = get_or_create_subscriber(session=db_session, chat_id=11223344)
    db_session.commit()
    assert sub.is_active is True

    # Deactivate (e.g. user sends /stop or blocks bot)
    deactivated = deactivate_subscriber(session=db_session, chat_id=11223344)
    db_session.commit()
    assert deactivated is True

    retrieved = get_subscriber_by_chat_id(db_session, 11223344)
    assert retrieved is not None
    assert retrieved.is_active is False

    # Deactivating again returns False (already inactive)
    assert deactivate_subscriber(session=db_session, chat_id=11223344) is False

    # Reactivate via /start
    sub_reactivated, created = get_or_create_subscriber(session=db_session, chat_id=11223344)
    db_session.commit()
    assert created is False
    assert sub_reactivated.is_active is True


def test_get_active_subscribers(db_session: Session):
    """Verify get_active_subscribers returns only users where is_active is True."""
    get_or_create_subscriber(session=db_session, chat_id=101, username="user1")
    get_or_create_subscriber(session=db_session, chat_id=102, username="user2")
    get_or_create_subscriber(session=db_session, chat_id=103, username="user3")
    deactivate_subscriber(session=db_session, chat_id=102)
    db_session.commit()

    active = get_active_subscribers(db_session)
    active_chat_ids = [s.chat_id for s in active]
    assert active_chat_ids == [101, 103]
