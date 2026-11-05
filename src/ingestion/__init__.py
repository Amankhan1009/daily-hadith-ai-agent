"""
Domain Ingestion and Deterministic Validation Package.
"""

from src.ingestion.service import (
    BatchIngestionSummary,
    CandidateIngestionService,
    IngestionResult,
    ingest_candidate_pair,
)

__all__ = [
    "CandidateIngestionService",
    "IngestionResult",
    "BatchIngestionSummary",
    "ingest_candidate_pair",
]
