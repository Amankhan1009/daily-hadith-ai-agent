"""
Automated Unit and Invariant Tests for Per-Subscriber Daily Idempotency and Mid-Run Recovery.
"""

from collections.abc import Generator
from datetime import date
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.database.models import HadithCandidate, SubscriberDeliveryLog
from src.database.repository import (
    get_or_create_subscriber,
    get_undelivered_active_subscribers,
    is_subscriber_delivered,
    record_subscriber_delivery,
    save_candidate,
)
from src.database.session import Base
from src.delivery import TelegramClient
from src.workflow import run_daily_workflow


@pytest.fixture
def test_db_session() -> Generator[Session]:
    """Provides an isolated in-memory SQLite database session."""
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
def seed_candidate(test_db_session: Session) -> HadithCandidate:
    cand = save_candidate(
        session=test_db_session,
        source_id="5913",
        collection="Sahih al-Bukhari",
        hadith_number="5027",
        english_title="Learn Quran",
        english_text="The best among you learn the Quran.",
        arabic_text="خيركم من تعلم القرآن",
        attribution="Narrated by Al-Bukhari",
        grade="Authentic",
        source_url="https://hadeethenc.com/en/browse/hadith/5913",
        verification_status="VERIFIED",
    )
    test_db_session.commit()
    return cand


def test_subscriber_daily_unique_constraint(
    test_db_session: Session, seed_candidate: HadithCandidate
):
    """
    Verify physical database constraint: inserting two delivery logs for the
    exact same (subscriber_id, scheduled_date) raises an IntegrityError.
    """
    sub, _ = get_or_create_subscriber(test_db_session, chat_id=111)
    test_db_session.commit()
    target_date = date(2026, 11, 26)

    # First log succeeds
    log1 = SubscriberDeliveryLog(
        subscriber_id=sub.id,
        chat_id=sub.chat_id,
        scheduled_date=target_date,
        candidate_id=seed_candidate.id,
        status="DELIVERED",
    )
    test_db_session.add(log1)
    test_db_session.commit()

    # Second log for same subscriber and same date violates UNIQUE constraint
    log2 = SubscriberDeliveryLog(
        subscriber_id=sub.id,
        chat_id=sub.chat_id,
        scheduled_date=target_date,
        candidate_id=seed_candidate.id,
        status="DELIVERED",
    )
    test_db_session.add(log2)

    with pytest.raises(IntegrityError):
        test_db_session.commit()


def test_mid_run_crash_recovery_skips_delivered_subscribers(
    test_db_session: Session, seed_candidate: HadithCandidate
):
    """
    Scenario: Broadcast is sending to 3 subscribers (A, B, C).
    A and B receive the message, then a crash/interruption occurs before C.
    On retry on the same calendar day:
    - A and B MUST BE SKIPPED (zero duplicates).
    - ONLY C must receive the message.
    """
    target_date = date(2026, 11, 27)

    sub_a, _ = get_or_create_subscriber(test_db_session, chat_id=1001, username="user_a")
    sub_b, _ = get_or_create_subscriber(test_db_session, chat_id=1002, username="user_b")
    sub_c, _ = get_or_create_subscriber(test_db_session, chat_id=1003, username="user_c")
    test_db_session.commit()

    # Simulate that sub_a was already delivered in the previous partial run
    record_subscriber_delivery(
        session=test_db_session,
        subscriber_id=sub_a.id,
        chat_id=sub_a.chat_id,
        scheduled_date=target_date,
        candidate_id=seed_candidate.id,
        status="DELIVERED",
    )
    test_db_session.commit()

    # Verify query identifies only B and C as pending
    pending = get_undelivered_active_subscribers(test_db_session, target_date)
    assert [s.chat_id for s in pending] == [1002, 1003]

    # Track actual dispatches
    sent_to_chats = []
    mock_client = MagicMock(spec=TelegramClient)
    mock_client.bot_token = "MOCK_TOKEN"

    def mock_send(chat_id, text, **kwargs):
        sent_to_chats.append(chat_id)
        return {"message_id": 555}

    mock_client.send_message.side_effect = mock_send

    # Run workflow
    final_state = run_daily_workflow(
        scheduled_date=target_date,
        session=test_db_session,
        telegram_client=mock_client,
    )

    # sub_a was skipped, only sub_b and sub_c received messages!
    assert sent_to_chats == [1002, 1003]
    assert final_state["delivered_count"] == 2

    # Verify all 3 are now marked as delivered
    assert is_subscriber_delivered(test_db_session, sub_a.id, target_date) is True
    assert is_subscriber_delivered(test_db_session, sub_b.id, target_date) is True
    assert is_subscriber_delivered(test_db_session, sub_c.id, target_date) is True


def test_full_rerun_on_same_day_sends_zero_messages(
    test_db_session: Session, seed_candidate: HadithCandidate
):
    """
    Scenario: If all active subscribers have already received today's Hadith,
    a subsequent rerun sends exactly 0 messages.
    """
    target_date = date(2026, 11, 28)

    sub, _ = get_or_create_subscriber(test_db_session, chat_id=2001)
    record_subscriber_delivery(
        session=test_db_session,
        subscriber_id=sub.id,
        chat_id=sub.chat_id,
        scheduled_date=target_date,
        candidate_id=seed_candidate.id,
        status="DELIVERED",
    )
    test_db_session.commit()

    sent_calls = []
    mock_client = MagicMock(spec=TelegramClient)
    mock_client.bot_token = "MOCK_TOKEN"
    mock_client.send_message.side_effect = lambda chat_id, text, **kwargs: sent_calls.append(
        chat_id
    )

    final_state = run_daily_workflow(
        scheduled_date=target_date,
        session=test_db_session,
        telegram_client=mock_client,
    )

    # Zero messages sent!
    assert len(sent_calls) == 0
    assert final_state["delivered_count"] == 0
