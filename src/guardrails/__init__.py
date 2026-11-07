"""
Guardrails AI & Reflection Safety Verification Package.

Provides deterministic validation against hallucination, theological decrees,
sacred text leakage, and structural malformations.
"""

from src.guardrails.rules import (
    MAX_REFLECTION_WORDS,
    MAX_SOURCE_OVERLAP_RATIO,
    MIN_REFLECTION_WORDS,
    PROHIBITED_CITATION_PATTERNS,
    PROHIBITED_INFLAMMATORY_PATTERNS,
    PROHIBITED_LEGAL_PATTERNS,
)
from src.guardrails.validator import (
    GuardrailResult,
    ReflectionValidator,
    validate_reflection,
)

__all__ = [
    "GuardrailResult",
    "MAX_REFLECTION_WORDS",
    "MAX_SOURCE_OVERLAP_RATIO",
    "MIN_REFLECTION_WORDS",
    "PROHIBITED_CITATION_PATTERNS",
    "PROHIBITED_INFLAMMATORY_PATTERNS",
    "PROHIBITED_LEGAL_PATTERNS",
    "ReflectionValidator",
    "validate_reflection",
]
