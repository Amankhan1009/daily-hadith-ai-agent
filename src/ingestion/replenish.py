"""
Automated Candidate Replenishment Engine.

Checks current pool of verified, undelivered Hadith candidates and
automatically ingests fresh batches from approved HadeethEnc categories
to guarantee the candidate queue never runs dry.
"""

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.database.models import DailyDeliveryLog, HadithCandidate
from src.database.session import get_db_session
from src.ingestion.service import CandidateIngestionService

logger = logging.getLogger("replenish")

APPROVED_CATEGORIES = [5, 1, 7]  # Virtues & Manners (5), Qur'anic Sciences (1), Seerah (7)
DEFAULT_MIN_THRESHOLD = 30  # Trigger replenishment if below this count
DEFAULT_TARGET_BUFFER = 90  # Refill until at least this many verified candidates are ready


def get_verified_undelivered_count(session: Session) -> int:
    """Return count of verified candidates not yet delivered to subscribers."""
    delivered_candidate_ids = (
        select(DailyDeliveryLog.candidate_id)
        .where(DailyDeliveryLog.status == "SUCCESS")
        .where(DailyDeliveryLog.candidate_id.is_not(None))
    )
    stmt = (
        select(func.count(HadithCandidate.id))
        .where(HadithCandidate.verification_status == "VERIFIED")
        .where(HadithCandidate.id.not_in(delivered_candidate_ids))
    )
    return session.execute(stmt).scalar_one()


def replenish_candidate_pool(
    session: Session,
    min_threshold: int = DEFAULT_MIN_THRESHOLD,
    target_buffer: int = DEFAULT_TARGET_BUFFER,
    max_pages_per_run: int = 5,
) -> dict[str, Any]:
    """
    Check pool depth and ingest fresh candidates if below threshold.

    Args:
        session: Active SQLAlchemy database session.
        min_threshold: Minimum buffer count before replenishment triggers.
        target_buffer: Desired count of verified candidates to achieve.
        max_pages_per_run: Safety ceiling on pages scanned per execution.

    Returns:
        dict[str, Any]: Summary metrics for the replenishment run.
    """
    initial_count = get_verified_undelivered_count(session)
    logger.info("Current verified undelivered candidate count: %d", initial_count)

    if initial_count >= min_threshold:
        logger.info(
            "Candidate pool depth (%d) meets threshold (%d). No replenishment required.",
            initial_count,
            min_threshold,
        )
        return {
            "status": "SKIPPED_SUFFICIENT",
            "initial_count": initial_count,
            "final_count": initial_count,
            "newly_verified": 0,
            "pages_processed": 0,
        }

    service = CandidateIngestionService()
    newly_verified_total = 0
    pages_processed = 0

    for cat_id in APPROVED_CATEGORIES:
        for page in range(1, 35):
            current_total = initial_count + newly_verified_total
            if current_total >= target_buffer or pages_processed >= max_pages_per_run:
                break

            logger.info("Scanning Category %d, Page %d for authentic candidates...", cat_id, page)
            summary = service.ingest_category_batch(
                session, category_id=cat_id, page=page, per_page=20
            )
            pages_processed += 1
            newly_verified_total += summary.newly_verified

            # If page had zero items, category is exhausted; move to next
            if summary.total_scanned == 0:
                break

        if (
            initial_count + newly_verified_total
        ) >= target_buffer or pages_processed >= max_pages_per_run:
            break

    final_count = get_verified_undelivered_count(session)
    logger.info(
        "Replenishment complete: +%d newly verified added across %d pages. Total now: %d",
        newly_verified_total,
        pages_processed,
        final_count,
    )

    return {
        "status": "REPLENISHED",
        "initial_count": initial_count,
        "final_count": final_count,
        "newly_verified": newly_verified_total,
        "pages_processed": pages_processed,
    }


def auto_replenish_background_task(
    min_threshold: int = 20,
    target_buffer: int = 60,
    max_pages_per_run: int = 3,
) -> None:
    """
    Safe background task invoked post-broadcast by FastAPI to ensure pool depth.
    Catches all exceptions to ensure fail-safe background execution.
    """
    try:
        with get_db_session() as session:
            result = replenish_candidate_pool(
                session,
                min_threshold=min_threshold,
                target_buffer=target_buffer,
                max_pages_per_run=max_pages_per_run,
            )
            logger.info("Background replenishment task result: %s", result)
    except Exception as exc:
        logger.warning("Background replenishment task encountered non-fatal error: %s", exc)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    with get_db_session() as db_session:
        res = replenish_candidate_pool(db_session)
        print("Replenishment Result:", res)
