"""
Automated Unit and Integration Tests for Candidate Ingestion and Validation Service.
"""

from collections.abc import Generator
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.database.models import HadithCandidate
from src.database.repository import get_candidate_by_source_id
from src.database.session import Base
from src.hadeethenc.client import HadeethEncClient
from src.hadeethenc.schemas import (
    HadeethEncArabicDetail,
    HadeethEncCandidatePair,
    HadeethEncEnglishDetail,
    HadeethEncListItem,
    HadeethEncListResponse,
    HadeethEncPaginationMeta,
)
from src.ingestion.service import (
    CandidateIngestionService,
    ingest_candidate_pair,
)


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
def valid_bukhari_pair() -> HadeethEncCandidatePair:
    """Fixture returning a valid, authentic Sahih al-Bukhari candidate pair."""
    en = HadeethEncEnglishDetail(
        id="5913",
        title="The best of you learn Quran and teach it",
        hadeeth="The best of you are those who learn the Qur'an and teach it.",
        attribution="Narrated by Al-Bukhari",
        grade="Authentic",
        hadeeth_ar="«خيركم من تعلم القرآن وعلمه»",
        attribution_ar="رواه البخاري",
        grade_ar="صحيح",
    )
    ar = HadeethEncArabicDetail(
        id="5913",
        title="خيركم",
        hadeeth="«خيركم من تعلم القرآن وعلمه»",
        attribution="رواه البخاري",
        grade="صحيح",
        reference="صحيح البخاري (6/ 192) (5027)",
    )
    return HadeethEncCandidatePair(
        source_id="5913",
        english=en,
        arabic=ar,
        canonical_url="https://hadeethenc.com/en/browse/hadith/5913",
    )


@pytest.fixture
def unapproved_collection_pair() -> HadeethEncCandidatePair:
    """Fixture returning a Hadith from an unapproved collection (At-Tirmidhi)."""
    en = HadeethEncEnglishDetail(
        id="66541",
        title="Keep your tongue moist with remembrance",
        hadeeth="A man said: O Messenger of Allah...",
        attribution="Narrated by At-Tirmidhi",
        grade="Authentic",
        hadeeth_ar="«لا يزال لسانك رطبا من ذكر الله»",
        attribution_ar="رواه الترمذي",
        grade_ar="صحيح",
    )
    ar = HadeethEncArabicDetail(
        id="66541",
        title="ذكر الله",
        hadeeth="«لا يزال لسانك رطبا من ذكر الله»",
        attribution="رواه الترمذي",
        grade="صحيح",
        reference="سنن الترمذي (5/ 458) (3375)",
    )
    return HadeethEncCandidatePair(
        source_id="66541",
        english=en,
        arabic=ar,
        canonical_url="https://hadeethenc.com/en/browse/hadith/66541",
    )


def test_ingest_valid_candidate_persists_verified(
    db_session: Session, valid_bukhari_pair: HadeethEncCandidatePair
):
    """Verify that a valid candidate is deterministically verified and saved as VERIFIED."""
    result = ingest_candidate_pair(db_session, valid_bukhari_pair)

    assert result.status == "INGESTED_VERIFIED"
    assert result.collection == "Sahih al-Bukhari"
    assert result.hadith_number == "5027"
    assert result.rejection_reason is None

    # Check database persistence
    stored = get_candidate_by_source_id(db_session, "5913")
    assert stored is not None
    assert stored.verification_status == "VERIFIED"
    assert stored.collection == "Sahih al-Bukhari"
    assert stored.hadith_number == "5027"
    assert stored.english_title == valid_bukhari_pair.english.title
    assert stored.rejection_reason is None


def test_ingest_unapproved_candidate_persists_rejected_audit(
    db_session: Session, unapproved_collection_pair: HadeethEncCandidatePair
):
    """Verify that an unapproved candidate is saved as REJECTED with full audit trail."""
    result = ingest_candidate_pair(db_session, unapproved_collection_pair)

    assert result.status == "INGESTED_REJECTED"
    assert result.collection == "Unverified"
    assert result.hadith_number is None
    assert "ERR_UNAPPROVED_COLLECTION" in (result.rejection_reason or "")

    # Check database persistence of audit trail
    stored = get_candidate_by_source_id(db_session, "66541")
    assert stored is not None
    assert stored.verification_status == "REJECTED"
    assert "ERR_UNAPPROVED_COLLECTION" in (stored.rejection_reason or "")
    assert stored.hadith_number is None


def test_ingest_candidate_skips_existing_idempotent(
    db_session: Session, valid_bukhari_pair: HadeethEncCandidatePair
):
    """Verify that re-ingesting an already stored candidate returns SKIPPED_EXISTING."""
    # First ingestion
    first_res = ingest_candidate_pair(db_session, valid_bukhari_pair)
    assert first_res.status == "INGESTED_VERIFIED"

    # Second ingestion without force_reverify
    second_res = ingest_candidate_pair(db_session, valid_bukhari_pair, force_reverify=False)
    assert second_res.status == "SKIPPED_EXISTING"
    assert second_res.candidate_id == first_res.candidate_id

    # Verify no duplicate entries were created
    candidates = db_session.query(HadithCandidate).filter(HadithCandidate.source_id == "5913").all()
    assert len(candidates) == 1


def test_ingest_category_batch_workflow(
    db_session: Session,
    valid_bukhari_pair: HadeethEncCandidatePair,
    unapproved_collection_pair: HadeethEncCandidatePair,
):
    """Verify that CandidateIngestionService batch processes category candidates and computes accurate metrics."""
    # 1. Pre-seed DB with one candidate to test deduplication during batch
    ingest_candidate_pair(db_session, valid_bukhari_pair)

    # 2. Mock HadeethEncClient
    mock_client = MagicMock(spec=HadeethEncClient)

    # Mock category listing returning 3 items
    mock_client.get_hadiths_by_category.return_value = HadeethEncListResponse(
        data=[
            HadeethEncListItem(id="5913", title="Best of you", translations=["en", "ar"]),
            HadeethEncListItem(
                id="66541",
                title="Keep tongue moist",
                translations=["en", "ar"],
            ),
            HadeethEncListItem(id="9999", title="Error candidate", translations=["en", "ar"]),
        ],
        meta=HadeethEncPaginationMeta(
            current_page="1",
            last_page=1,
            total_items=3,
            per_page="20",
        ),
    )

    # Mock get_candidate_pair responses
    def mock_get_pair(source_id: str):
        if str(source_id) == "66541":
            return unapproved_collection_pair
        raise RuntimeError("Network failure simulating broken candidate")

    mock_client.get_candidate_pair.side_effect = mock_get_pair

    # 3. Run batch ingestion
    service = CandidateIngestionService(client=mock_client)
    summary = service.ingest_category_batch(session=db_session, category_id=5, page=1, per_page=20)

    assert summary.total_scanned == 3
    assert summary.already_existed == 1  # 5913 was pre-seeded
    assert summary.newly_rejected == 1  # 66541 was rejected
    assert summary.newly_verified == 0
    assert summary.failed_requests == 1  # 9999 raised exception


def test_replenish_candidate_pool_skipped_when_sufficient(db_session: Session):
    """Test replenish_candidate_pool skips when pool count meets min_threshold."""
    from src.database.models import HadithCandidate
    from src.ingestion.replenish import replenish_candidate_pool

    # Seed 3 verified candidates
    for i in range(1, 4):
        c = HadithCandidate(
            source_id=f"src_{i}",
            collection="Sahih al-Bukhari",
            hadith_number=str(i),
            english_title=f"Title {i}",
            english_text=f"Text {i}",
            arabic_text=f"Arabic {i}",
            attribution="Bukhari",
            grade="Authentic",
            source_url="https://hadeethenc.com",
            verification_status="VERIFIED",
        )
        db_session.add(c)
    db_session.commit()

    # Threshold of 2: current is 3, should skip
    res = replenish_candidate_pool(db_session, min_threshold=2, target_buffer=5)
    assert res["status"] == "SKIPPED_SUFFICIENT"
    assert res["initial_count"] == 3
    assert res["newly_verified"] == 0


def test_auto_replenish_background_task_fail_safe():
    """Test that auto_replenish_background_task catches any exceptions gracefully."""
    from unittest.mock import patch

    from src.ingestion.replenish import auto_replenish_background_task

    with patch("src.ingestion.replenish.get_db_session", side_effect=RuntimeError("DB down")):
        # Should NOT raise, fail-safe
        auto_replenish_background_task()
