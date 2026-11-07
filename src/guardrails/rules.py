"""
Guardrail Rules and Boundary Patterns for AI Reflections.

Defines deterministic negative constraints, prohibited theological declarations,
citation leakage regexes, and structural boundary limits.
"""

import re
from re import Pattern

# Maximum and minimum word boundaries for concise, educational reflections
MIN_REFLECTION_WORDS: int = 8
MAX_REFLECTION_WORDS: int = 150

# Maximum permitted word overlap ratio between reflection and source Hadith text
MAX_SOURCE_OVERLAP_RATIO: float = 0.40

# Prohibited theological decree patterns (No Fatwas / Binding Jurisprudence)
PROHIBITED_LEGAL_PATTERNS: list[Pattern] = [
    re.compile(
        r"\b(?:i\s+(?:hereby\s+)?decree|the\s+ruling\s+is|a\s+binding\s+fatwa)\b", re.IGNORECASE
    ),
    re.compile(r"\b(?:issue\s+a\s+fatwa|this\s+fatwa\s+states)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:penalty\s+under\s+(?:sharia|islamic\s+law)|punishable\s+by\s+death)\b", re.IGNORECASE
    ),
    re.compile(
        r"\b(?:it\s+is\s+(?:hereby\s+)?(?:declared\s+)?(?:strictly\s+)?(?:haram|halal)\s+for\s+all)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:as\s+a\s+mufti|in\s+my\s+scholarly\s+authority)\b", re.IGNORECASE),
]

# Prohibited citation patterns (AI reflection must not fabricate or re-cite sources)
PROHIBITED_CITATION_PATTERNS: list[Pattern] = [
    re.compile(
        r"\b(?:recorded|reported|found|documented)\s+in\s+(?:sahih|sunan|jami|musnad)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:hadith\s+number|hadith\s+no\.?|vol(?:ume)?\.?\s*\d+)\b", re.IGNORECASE),
    re.compile(r"\b(?:chain\s+of\s+narration|isnad\s+is)\b", re.IGNORECASE),
]

# Prohibited inflammatory or sectarian rhetoric patterns
PROHIBITED_INFLAMMATORY_PATTERNS: list[Pattern] = [
    re.compile(r"\b(?:kafir|kuffar|apostate|infidel|heretic|deviant\s+sect)\b", re.IGNORECASE),
    re.compile(r"\b(?:curse\s+upon|destroy\s+the|enemies\s+of\s+allah)\b", re.IGNORECASE),
]
