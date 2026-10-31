"""
Deterministic Invariant Verifier and Reference Extractor.

Enforces cross-matching invariants between English and Arabic records and
extracts canonical collection references using deterministic regex grammar.
"""

from dataclasses import dataclass
import re
from typing import Optional

from src.hadeethenc.schemas import HadeethEncCandidatePair

# Deterministic Arabic citation patterns matching docs/API_CONTRACTS.md
BUKHARI_PATTERN = re.compile(r"صحيح البخاري(?:\s*\(\d+/\s*\d+\))?\s*\((\d+)\)")
MUSLIM_PATTERN = re.compile(r"صحيح مسلم(?:\s*\(\d+/\s*\d+\))?\s*\((\d+)\)")


@dataclass(frozen=True)
class VerificationResult:
    """
    Structured outcome of deterministic candidate verification.
    """

    is_valid: bool
    collection: Optional[str] = None
    hadith_number: Optional[str] = None
    rejection_reason: Optional[str] = None


def normalize_arabic_text(text: str) -> str:
    """
    Normalize Arabic text for comparison by stripping whitespace and common wrappers.
    """
    if not text:
        return ""
    # Remove outer quotation marks and trim
    cleaned = text.strip().strip("«»\"'").strip()
    # Normalize multiple whitespace characters into a single space
    return " ".join(cleaned.split())


def extract_collection_and_reference(
    attribution_ar: str, reference_text: str
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Parse Arabic attribution and multi-line citation to resolve approved collection and reference number.
    Returns: (collection, hadith_number, rejection_reason)
    """
    bukhari_match = BUKHARI_PATTERN.search(reference_text)
    muslim_match = MUSLIM_PATTERN.search(reference_text)

    is_agreed_upon = "متفق عليه" in attribution_ar or (bukhari_match and muslim_match)

    if is_agreed_upon:
        # For Agreed Upon, prioritize the Bukhari or Muslim number available
        num = None
        if bukhari_match:
            num = bukhari_match.group(1)
        elif muslim_match:
            num = muslim_match.group(1)
        return "Agreed Upon (Al-Bukhari & Muslim)", num, None

    if bukhari_match:
        return "Sahih al-Bukhari", bukhari_match.group(1), None

    if muslim_match:
        return "Sahih Muslim", muslim_match.group(1), None

    if "البخاري" in attribution_ar or "مسلم" in attribution_ar:
        return None, None, "ERR_AMBIGUOUS_CITATION: Attribution mentions approved collection but citation lacks canonical Hadith number"

    # If it cites neither Bukhari nor Muslim, reject for V1
    return None, None, "ERR_UNAPPROVED_COLLECTION: Candidate does not cite Sahih al-Bukhari or Sahih Muslim"


def verify_candidate_pair(pair: HadeethEncCandidatePair) -> VerificationResult:
    """
    Execute deterministic validation gatekeeper on a candidate pair:
    1. Check ID invariance.
    2. Check Arabic text invariance (en.hadeeth_ar == ar.hadeeth).
    3. Check Attribution invariance (en.attribution_ar == ar.attribution).
    4. Extract and verify collection membership.
    """
    # Invariant 1: ID Match
    if str(pair.english.id) != str(pair.arabic.id):
        return VerificationResult(
            is_valid=False,
            rejection_reason=f"ERR_RECORD_MISMATCH: ID mismatch ({pair.english.id} != {pair.arabic.id})",
        )

    # Invariant 2: Arabic Text Invariance
    norm_en_ar = normalize_arabic_text(pair.english.hadeeth_ar)
    norm_ar_ar = normalize_arabic_text(pair.arabic.hadeeth)

    if norm_en_ar != norm_ar_ar:
        return VerificationResult(
            is_valid=False,
            rejection_reason="ERR_RECORD_MISMATCH: Embedded English Arabic text does not match Arabic payload text",
        )

    # Invariant 3: Attribution Consistency
    norm_attr_en = normalize_arabic_text(pair.english.attribution_ar)
    norm_attr_ar = normalize_arabic_text(pair.arabic.attribution)

    if norm_attr_en != norm_attr_ar:
        return VerificationResult(
            is_valid=False,
            rejection_reason="ERR_RECORD_MISMATCH: Attribution mismatch between English and Arabic records",
        )

    # Invariant 4: Mandatory Reference Existence
    if not pair.arabic.reference or not pair.arabic.reference.strip():
        return VerificationResult(
            is_valid=False,
            rejection_reason="ERR_MISSING_REFERENCE: Authoritative Arabic reference citation is empty",
        )

    # Invariant 5: Collection & Reference Number Extraction
    collection, hadith_number, rejection_reason = extract_collection_and_reference(
        attribution_ar=pair.arabic.attribution,
        reference_text=pair.arabic.reference,
    )

    if rejection_reason is not None or collection is None:
        return VerificationResult(
            is_valid=False,
            rejection_reason=rejection_reason or "ERR_AMBIGUOUS_CITATION",
        )

    # All deterministic invariants passed
    return VerificationResult(
        is_valid=True,
        collection=collection,
        hadith_number=hadith_number,
        rejection_reason=None,
    )