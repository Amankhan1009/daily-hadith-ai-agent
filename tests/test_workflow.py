"""
Automated Unit Tests for LangGraph StateGraph Workflow and Routing Logic.
"""

from collections.abc import Generator
from datetime import date
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.database.repository import (
    get_or_create_subscriber,
    get_subscriber_by_chat_id,
    is_date_delivered,
    record_delivery_log,
    save_candidate,
)
from src.database.session import Base
from src.delivery import TelegramBotBlockedError, TelegramClient
from src.workflow import run_daily_workflow


@pytest.fixture
def db_session() -> Generator[Session]:
    """Provides an isolated in-memory SQLite database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def seed_verified_candidate(db_session: Session):
    """Seed the database with a verified Sahih al-Bukhari candidate."""
    return save_candidate(
        session=db_session,
        source_id="5913",
        collection="Sahih al-Bukhari",
        hadith_number="5027",
        english_title="The best of you learn Quran and teach it",
        english_text="The best of you are those who learn the Qur'an and teach it.",
        arabic_text="«خيركم من تعلم القرآن وعلمه»",
        attribution="Narrated by Al-Bukhari",
        grade="Authentic",
        source_url="https://hadeethenc.com/en/browse/hadith/5913",
        verification_status="VERIFIED",
    )


def test_workflow_happy_path_completes_delivery(db_session: Session, seed_verified_candidate):
    """
    Test 1 (Happy Path):
    Workflow checks idempotency, fetches verified candidate, passes safety gate,
    formats message, and records delivery in database.
    """
    test_date = date(2026, 11, 5)

    final_state = run_daily_workflow(scheduled_date=test_date, session=db_session)

    assert final_state["status"] == "COMPLETED"
    assert final_state["is_idempotent"] is False
    assert final_state["verification_passed"] is True
    assert final_state["candidate_id"] == seed_verified_candidate.id
    assert final_state["collection"] == "Sahih al-Bukhari"
    assert final_state["hadith_number"] == "5027"

    # Verify message formatting
    formatted = final_state.get("formatted_message", "")
    assert "Hadith of the Day" in formatted
    assert "The best of you are those who learn the Qur'an" in formatted
    assert "Sahih al-Bukhari (#5027)" in formatted
    assert "https://hadeethenc.com/en/browse/hadith/5913" in formatted

    # Verify database delivery log was recorded
    assert is_date_delivered(db_session, test_date) is True


def test_workflow_idempotency_skip_route(db_session: Session, seed_verified_candidate):
    """
    Test 2 (Idempotency Skip):
    If delivery already occurred on scheduled_date, graph terminates immediately
    with status SKIPPED_IDEMPOTENT and skips candidate fetch.
    """
    test_date = date(2026, 11, 5)

    # Pre-record a successful delivery
    record_delivery_log(session=db_session, scheduled_date=test_date, status="SUCCESS")
    db_session.commit()

    final_state = run_daily_workflow(scheduled_date=test_date, session=db_session)

    assert final_state["status"] == "SKIPPED_IDEMPOTENT"
    assert final_state["is_idempotent"] is True
    # Candidate should not have been fetched
    assert final_state.get("candidate_id") is None
    assert final_state.get("formatted_message") is None


def test_workflow_aborts_when_no_candidates_available(db_session: Session):
    """
    Test 3 (Queue Empty Abort):
    If no verified candidate exists in database, graph halts safely with
    ABORTED_NO_CANDIDATE.
    """
    test_date = date(2026, 11, 5)

    final_state = run_daily_workflow(scheduled_date=test_date, session=db_session)

    assert final_state["status"] == "ABORTED_NO_CANDIDATE"
    assert "No verified candidates" in (final_state.get("error_message") or "")
    assert final_state.get("candidate_id") is None
    assert is_date_delivered(db_session, test_date) is False


def test_workflow_safety_gate_rejects_unapproved_collection(db_session: Session):
    """
    Test 4 (Defense-in-Depth Safety Abort):
    If a candidate somehow has an unapproved collection in the queue,
    the safety gate stops it cold before formatting or delivery.
    """
    test_date = date(2026, 11, 5)

    # Seed an unapproved collection
    save_candidate(
        session=db_session,
        source_id="9999",
        collection="Sunan Abi Dawud",  # Unapproved for V1
        hadith_number="1234",
        english_title="Unapproved Hadith",
        english_text="Some text",
        arabic_text="نص",
        attribution="Narrated by Abu Dawud",
        grade="Good",
        source_url="https://url",
        verification_status="VERIFIED",  # Pretend it was marked verified by mistake
    )
    db_session.commit()

    final_state = run_daily_workflow(scheduled_date=test_date, session=db_session)

    assert final_state["status"] == "ABORTED_VALIDATION_FAILED"
    assert final_state["verification_passed"] is False
    assert "unapproved collection" in (final_state.get("error_message") or "")
    assert final_state.get("formatted_message") is None
    assert is_date_delivered(db_session, test_date) is False


def test_workflow_guardrail_omits_violating_reflection_while_delivering_hadith(
    db_session: Session, seed_verified_candidate
):
    """
    Test 5 (Guardrail Fail-Safe Omission):
    If the LLM returns an invalid reflection (e.g. issuing a theological fatwa),
    the guardrail node catches it, strips the reflection, and delivers the authentic Hadith cleanly.
    """
    from unittest.mock import MagicMock

    from src.llm import GroqReflectionClient, ReflectionResult

    test_date = date(2026, 11, 5)

    # Mock LLM client returning a prohibited theological fatwa
    mock_llm = MagicMock(spec=GroqReflectionClient)
    mock_llm.generate_reflection.return_value = ReflectionResult(
        reflection="• It is hereby declared strictly haram for all believers to neglect this.",
        status="GENERATED",
        model="openai/gpt-oss-120b",
    )

    final_state = run_daily_workflow(
        scheduled_date=test_date, session=db_session, llm_client=mock_llm
    )

    assert final_state["status"] == "COMPLETED"
    assert final_state["ai_reflection"] is None
    assert final_state["ai_reflection_status"] == "OMITTED_GUARDRAIL_FAILED"
    assert "Reflection & Practical Context" not in final_state["formatted_message"]
    assert "The best of you are those who learn the Qur'an" in final_state["formatted_message"]
    assert is_date_delivered(db_session, test_date) is True


def test_workflow_guardrail_allows_clean_reflection(db_session: Session, seed_verified_candidate):
    """
    Test 6 (Guardrail Clean Reflection Pass):
    Compliant reflection passes guardrail node and is rendered in the message.
    """
    from unittest.mock import MagicMock

    from src.llm import GroqReflectionClient, ReflectionResult

    test_date = date(2026, 11, 5)

    clean_reflection = (
        "• Commit dedicated time daily to studying and practicing sacred guidance.\n"
        "• Share beneficial understanding generously with family and peers.\n"
        "• Let continuous learning cultivate humility and patience in character."
    )
    mock_llm = MagicMock(spec=GroqReflectionClient)
    mock_llm.generate_reflection.return_value = ReflectionResult(
        reflection=clean_reflection,
        status="GENERATED",
        model="openai/gpt-oss-120b",
    )

    final_state = run_daily_workflow(
        scheduled_date=test_date, session=db_session, llm_client=mock_llm
    )

    assert final_state["status"] == "COMPLETED"
    assert final_state["ai_reflection"] is not None
    assert final_state["ai_reflection_status"] == "PASSED_GUARDRAILS"
    assert "💡 <b>Reflection & Practical Context:</b>" in final_state["formatted_message"]
    assert is_date_delivered(db_session, test_date) is True


def test_workflow_multi_user_fanout_and_block_deactivation(
    db_session: Session, seed_verified_candidate
):
    """
    Verify deliver_telegram node delivers to all active subscribers and
    automatically marks blocked users as inactive on HTTP 403.
    """
    test_date = date(2026, 11, 20)

    # Register 2 subscribers
    sub1, _ = get_or_create_subscriber(db_session, chat_id=11111, username="user1")
    sub2, _ = get_or_create_subscriber(db_session, chat_id=22222, username="user2")
    db_session.commit()

    # Mock TelegramClient: user1 succeeds, user2 blocks bot (HTTP 403)
    mock_client = MagicMock(spec=TelegramClient)
    mock_client.bot_token = "MOCK_TOKEN"

    def mock_send(chat_id, text, **kwargs):
        if chat_id == 22222:
            raise TelegramBotBlockedError(chat_id=22222, message="Forbidden: bot was blocked")
        return {"message_id": 777}

    mock_client.send_message.side_effect = mock_send

    final_state = run_daily_workflow(
        scheduled_date=test_date,
        session=db_session,
        telegram_client=mock_client,
    )

    assert final_state["status"] == "COMPLETED"
    assert final_state["subscribers_count"] == 2
    assert final_state["delivered_count"] == 1
    assert final_state["failed_count"] == 1

    # Verify sub2 was auto-deactivated in database
    db_session.expire_all()
    assert get_subscriber_by_chat_id(db_session, 11111).is_active is True
    assert get_subscriber_by_chat_id(db_session, 22222).is_active is False
