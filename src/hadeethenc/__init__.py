"""
HadeethEnc Integration Package.

Provides typed HTTP client methods, Pydantic response models, and deterministic
cross-matching verifiers for HadeethEnc API candidates.
"""

from src.hadeethenc.client import (
    HadeethEncClient,
    HadeethEncError,
    HadeethEncNetworkError,
    HadeethEncNotFoundError,
    HadeethEncResponseError,
)
from src.hadeethenc.schemas import (
    HadeethEncArabicDetail,
    HadeethEncCandidatePair,
    HadeethEncEnglishDetail,
    HadeethEncListItem,
    HadeethEncListResponse,
)
from src.hadeethenc.verifier import (
    VerificationResult,
    extract_collection_and_reference,
    normalize_arabic_text,
    verify_candidate_pair,
)

__all__ = [
    "HadeethEncArabicDetail",
    "HadeethEncCandidatePair",
    "HadeethEncClient",
    "HadeethEncEnglishDetail",
    "HadeethEncError",
    "HadeethEncListItem",
    "HadeethEncListResponse",
    "HadeethEncNetworkError",
    "HadeethEncNotFoundError",
    "HadeethEncResponseError",
    "VerificationResult",
    "extract_collection_and_reference",
    "normalize_arabic_text",
    "verify_candidate_pair",
]
