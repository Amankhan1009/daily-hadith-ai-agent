"""
Automated Unit Tests for Database Repositories and Idempotency Invariants.
"""

from collections.abc import Generator
from datetime import date, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from src.database.models import DailyDeliveryLog, HadithCandidate
from src.database.repository import (
    get_candidate_by_source_id,
    get_next_verified_candidate,
    is_date_delivered,
    record_delivery_log,
    save_candidate,
)
from src.database.session import Base


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
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