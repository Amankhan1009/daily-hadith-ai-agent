"""
Deterministic Reflection Validator and Guardrail Verification Engine.

Enforces strict theological negative constraints, citation bounds,
length boundaries, and sacred text invariance on LLM commentary.
"""

from dataclasses import dataclass
import logging
import re
from typing import Optional

from src.guardrails.rules import (
    MAX_REFLECTION_WORDS,
    MAX_SOURCE_OVERLAP_RATIO,
    MIN_REFLECTION_WORDS,
    PROHIBITED_CITATION_PATTERNS,
    PROHIBITED_INFLAMMATORY_PATTERNS,
    PROHIBITED_LEGAL_PATTERNS,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GuardrailResult:
    """Outcome of a reflection guardrail validation check."""

    is_valid: bool
    status: str  # "PASSED" | "REJECTED"
    error_code: Optional[str] = None
    reason: Optional[str] = None
    sanitized_text: Optional[str] = None


class ReflectionValidator:
    """
    Deterministic validator enforcing safety guardrails on AI-generated reflections.
    """

    def validate(
        self,
        reflection: Optional[str],
        source_hadith_text: Optional[str] = None,
    ) -> GuardrailResult:
        """
        Run comprehensive structural, theological, and content guardrails.
        """
        if not reflection or not reflection.strip():
            return GuardrailResult(
                is_valid=False,
                status="REJECTED",
                error_code="ERR_EMPTY_REFLECTION",
                reason="Reflection payload is empty or whitespace only.",
            )

        cleaned = reflection.strip()
        words = re.findall(r"\b\w+\b", cleaned)
        word_count = len(words)

        # 1. Word Count Boundary Check
        if word_count < MIN_REFLECTION_WORDS:
            return GuardrailResult(
                is_valid=False,
                status="REJECTED",
                error_code="ERR_REFLECTION_TOO_SHORT",
                reason=f"Reflection has only {word_count} words (minimum required: {MIN_REFLECTION_WORDS}).",
            )

        if word_count > MAX_REFLECTION_WORDS:
            return GuardrailResult(
                is_valid=False,
                status="REJECTED",
                error_code="ERR_REFLECTION_TOO_LONG",
                reason=f"Reflection has {word_count} words (maximum allowed: {MAX_REFLECTION_WORDS}).",
            )

        # 2. Structural Bullet Check (Must contain bullet-style practical takeaways)
        has_bullets = bool(
            re.search(r"^\s*[-•*]\s+", cleaned, re.MULTILINE)
            or re.search(r"^\s*\d+[\.\)]\s+", cleaned, re.MULTILINE)
        )
        if not has_bullets:
            return GuardrailResult(
                is_valid=False,
                status="REJECTED",
                error_code="ERR_MISSING_BULLET_STRUCTURE",
                reason="Reflection must be formatted with bulleted practical takeaways.",
            )

        # 3. Prohibited Theological Decrees (Fatwas / Rulings)
        for pattern in PROHIBITED_LEGAL_PATTERNS:
            match = pattern.search(cleaned)
            if match:
                matched_term = match.group(0)
                logger.warning("Guardrail tripped: Theological decree pattern '%s' detected.", matched_term)
                return GuardrailResult(
                    is_valid=False,
                    status="REJECTED",
                    error_code="ERR_THEOLOGICAL_DECREE",
                    reason=f"Reflection violates theological decree boundary: '{matched_term}'.",
                )

        # 4. Prohibited Citation / Fabrication Patterns
        for pattern in PROHIBITED_CITATION_PATTERNS:
            match = pattern.search(cleaned)
            if match:
                matched_term = match.group(0)
                logger.warning("Guardrail tripped: Citation pattern '%s' detected in reflection.", matched_term)
                return GuardrailResult(
                    is_valid=False,
                    status="REJECTED",
                    error_code="ERR_UNAUTHORIZED_CITATION",
                    reason=f"Reflection contains unauthorized source citation: '{matched_term}'.",
                )

        # 5. Prohibited Inflammatory / Sectarian Patterns
        for pattern in PROHIBITED_INFLAMMATORY_PATTERNS:
            match = pattern.search(cleaned)
            if match:
                matched_term = match.group(0)
                logger.warning("Guardrail tripped: Inflammatory pattern '%s' detected.", matched_term)
                return GuardrailResult(
                    is_valid=False,
                    status="REJECTED",
                    error_code="ERR_INFLAMMATORY_LANGUAGE",
                    reason=f"Reflection contains prohibited inflammatory language: '{matched_term}'.",
                )

        # 6. Sacred Hadith Text Overlap & Leakage Check
        if source_hadith_text and source_hadith_text.strip():
            leakage_result = self._check_text_leakage(cleaned, source_hadith_text)
            if not leakage_result.is_valid:
                return leakage_result

        return GuardrailResult(
            is_valid=True,
            status="PASSED",
            sanitized_text=cleaned,
        )

    def _check_text_leakage(self, reflection: str, hadith_text: str) -> GuardrailResult:
        """
        Verify that the AI reflection does not paraphrase or repeat sacred text verbatim.
        """
        ref_words = [w.lower() for w in re.findall(r"\b\w+\b", reflection)]
        src_words = [w.lower() for w in re.findall(r"\b\w+\b", hadith_text)]

        # Check for 8+ consecutive word exact match from Hadith in reflection
        window_size = 8
        if len(src_words) >= window_size and len(ref_words) >= window_size:
            src_phrases = {
                " ".join(src_words[i : i + window_size])
                for i in range(len(src_words) - window_size + 1)
            }
            for j in range(len(ref_words) - window_size + 1):
                ref_phrase = " ".join(ref_words[j : j + window_size])
                if ref_phrase in src_phrases:
                    return GuardrailResult(
                        is_valid=False,
                        status="REJECTED",
                        error_code="ERR_HADITH_TEXT_LEAKAGE",
                        reason=f"Reflection repeats Hadith text verbatim: '...{ref_phrase}...'."
                    )

        # Check vocabulary overlap ratio (excluding stop words)
        stop_words = {
            "the", "and", "to", "of", "a", "in", "is", "that", "for", "it",
            "as", "was", "with", "be", "by", "on", "not", "he", "i", "this",
            "at", "or", "his", "from", "you", "are", "we", "an", "your",
        }
        ref_vocab = set(ref_words) - stop_words
        src_vocab = set(src_words) - stop_words

        if ref_vocab and src_vocab:
            overlap = ref_vocab.intersection(src_vocab)
            ratio = len(overlap) / len(ref_vocab)
            if ratio > MAX_SOURCE_OVERLAP_RATIO:
                return GuardrailResult(
                    is_valid=False,
                    status="REJECTED",
                    error_code="ERR_HIGH_VOCAB_OVERLAP",
                    reason=f"Reflection has excessive vocabulary overlap with Hadith ({ratio:.1%} > {MAX_SOURCE_OVERLAP_RATIO:.1%}).",
                )

        return GuardrailResult(is_valid=True, status="PASSED")


# Default singleton validator
_default_validator = ReflectionValidator()


def validate_reflection(
    reflection: Optional[str],
    source_hadith_text: Optional[str] = None,
) -> GuardrailResult:
    """Convenience helper to validate a reflection using the default validator."""
    return _default_validator.validate(reflection, source_hadith_text)

