"""
Candidate Ingestion and Deterministic Validation Service.

Coordinates HadeethEnc API retrieval, deterministic invariant verification,
database deduplication, and structured candidate persistence.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.database.repository import get_candidate_by_source_id, save_candidate
from src.hadeethenc.client import HadeethEncClient
from src.hadeethenc.schemas import HadeethEncCandidatePair
from src.hadeethenc.verifier import verify_candidate_pair


@dataclass(frozen=True)
class IngestionResult:
    """Result of ingesting a single Hadith candidate."""

    source_id: str
    status: str  # 'INGESTED_VERIFIED' | 'INGESTED_REJECTED' | 'SKIPPED_EXISTING'
    candidate_id: int | None = None
    collection: str | None = None
    hadith_number: str | None = None
    rejection_reason: str | None = None


@dataclass(frozen=True)
class BatchIngestionSummary:
    """Summary metrics for a batch candidate ingestion run."""

    total_scanned: int
    newly_verified: int
    newly_rejected: int
    already_existed: int
    failed_requests: int


def ingest_candidate_pair(
    session: Session,
    pair: HadeethEncCandidatePair,
    force_reverify: bool = False,
) -> IngestionResult:
    """
    Deterministically verify a candidate pair and persist it to the database.

    If candidate already exists and force_reverify is False, returns SKIPPED_EXISTING.
    Otherwise, runs deterministic verifier and records status (VERIFIED or REJECTED).
    """
    existing = get_candidate_by_source_id(session, pair.source_id)
    if existing is not None and not force_reverify:
        return IngestionResult(
            source_id=pair.source_id,
            status="SKIPPED_EXISTING",
            candidate_id=existing.id,
            collection=existing.collection,
            hadith_number=existing.hadith_number,
            rejection_reason=existing.rejection_reason,
        )

    # Execute deterministic gatekeeper
    verif = verify_candidate_pair(pair)

    if verif.is_valid:
        collection = verif.collection or "Unknown Collection"
        hadith_number = verif.hadith_number
        verification_status = "VERIFIED"
        rejection_reason = None
        status_label = "INGESTED_VERIFIED"
    else:
        collection = "Unverified"
        hadith_number = None
        verification_status = "REJECTED"
        rejection_reason = verif.rejection_reason
        status_label = "INGESTED_REJECTED"

    candidate = save_candidate(
        session=session,
        source_id=pair.source_id,
        collection=collection,
        hadith_number=hadith_number,
        english_title=pair.english.title,
        english_text=pair.english.hadeeth,
        arabic_text=pair.arabic.hadeeth,
        attribution=pair.english.attribution,
        grade=pair.english.grade,
        source_url=pair.canonical_url,
        translation_version=None,
        verification_status=verification_status,
        rejection_reason=rejection_reason,
    )

    return IngestionResult(
        source_id=pair.source_id,
        status=status_label,
        candidate_id=candidate.id,
        collection=collection,
        hadith_number=hadith_number,
        rejection_reason=rejection_reason,
    )


class CandidateIngestionService:
    """
    High-level service coordinating HadeethEnc discovery, dual retrieval,
    verification, and persistence into the application database.
    """

    def __init__(self, client: HadeethEncClient | None = None) -> None:
        self.client = client or HadeethEncClient()
        self._owns_client = client is None

    def __enter__(self) -> "CandidateIngestionService":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._owns_client:
            self.client.close()

    def ingest_by_id(
        self,
        session: Session,
        source_id: str | int,
        force_reverify: bool = False,
    ) -> IngestionResult:
        """Fetch a single Hadith by ID, verify, and store."""
        pair = self.client.get_candidate_pair(source_id)
        return ingest_candidate_pair(session, pair, force_reverify=force_reverify)

    def ingest_category_batch(
        self,
        session: Session,
        category_id: int | str,
        page: int = 1,
        per_page: int = 20,
        max_to_process: int | None = None,
    ) -> BatchIngestionSummary:
        """
        Scan a category page, retrieve dual pairs, verify, and persist each candidate.
        """
        list_response = self.client.get_hadiths_by_category(
            category_id=category_id, page=page, per_page=per_page
        )

        total_scanned = 0
        newly_verified = 0
        newly_rejected = 0
        already_existed = 0
        failed_requests = 0

        items_to_process = list_response.data
        if max_to_process is not None:
            items_to_process = items_to_process[:max_to_process]

        for item in items_to_process:
            total_scanned += 1
            # Check fast deduplication before fetching counterpart
            existing = get_candidate_by_source_id(session, item.id)
            if existing is not None:
                already_existed += 1
                continue

            try:
                pair = self.client.get_candidate_pair(item.id)
                res = ingest_candidate_pair(session, pair)
                if res.status == "INGESTED_VERIFIED":
                    newly_verified += 1
                elif res.status == "INGESTED_REJECTED":
                    newly_rejected += 1
            except Exception:
                failed_requests += 1

        session.commit()

        return BatchIngestionSummary(
            total_scanned=total_scanned,
            newly_verified=newly_verified,
            newly_rejected=newly_rejected,
            already_existed=already_existed,
            failed_requests=failed_requests,
        )
