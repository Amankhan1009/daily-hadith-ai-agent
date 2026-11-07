"""
Automated Unit Tests for Guardrails AI Reflection Verification.
"""

import pytest

from src.guardrails import (
    ReflectionValidator,
    validate_reflection,
)


@pytest.fixture
def validator():
    return ReflectionValidator()


@pytest.fixture
def sample_hadith():
    return "Actions are judged by motives, so each man will have what he intended."


def test_valid_reflection_passes(validator, sample_hadith):
    """Verify that a compliant, practical reflection passes all guardrails."""
    valid_text = (
        "• Reflect deeply on personal intentions before embarking on daily work.\n"
        "• Practice mindfulness so mundane routines contribute to personal growth.\n"
        "• Periodically evaluate whether your actions align with sincere motives."
    )
    result = validator.validate(valid_text, sample_hadith)
    assert result.is_valid is True
    assert result.status == "PASSED"
    assert result.error_code is None
    assert result.sanitized_text == valid_text


def test_empty_or_whitespace_rejected(validator, sample_hadith):
    """Verify that empty or whitespace reflections are rejected."""
    result = validator.validate("   ", sample_hadith)
    assert result.is_valid is False
    assert result.status == "REJECTED"
    assert result.error_code == "ERR_EMPTY_REFLECTION"


def test_too_short_rejected(validator, sample_hadith):
    """Verify that reflections below minimum word count are rejected."""
    result = validator.validate("• Too short.", sample_hadith)
    assert result.is_valid is False
    assert result.error_code == "ERR_REFLECTION_TOO_SHORT"


def test_too_long_rejected(validator, sample_hadith):
    """Verify that verbose reflections exceeding maximum word count are rejected."""
    long_text = "• " + "word " * 160
    result = validator.validate(long_text, sample_hadith)
    assert result.is_valid is False
    assert result.error_code == "ERR_REFLECTION_TOO_LONG"


def test_missing_bullet_structure_rejected(validator, sample_hadith):
    """Verify that plain paragraphs without bullet formatting are rejected."""
    plain_text = (
        "This is an unformatted reflection that lacks any bullet points or numbered lists "
        "and is simply written as a continuous block of sentences without structure."
    )
    result = validator.validate(plain_text, sample_hadith)
    assert result.is_valid is False
    assert result.error_code == "ERR_MISSING_BULLET_STRUCTURE"


def test_theological_decree_rejected(validator, sample_hadith):
    """Verify that attempted fatwas or binding rulings trigger immediate rejection."""
    decree_text = (
        "• Here is advice for your morning.\n"
        "• It is hereby declared strictly haram for all believers to act otherwise.\n"
        "• Ensure you follow this rule."
    )
    result = validator.validate(decree_text, sample_hadith)
    assert result.is_valid is False
    assert result.error_code == "ERR_THEOLOGICAL_DECREE"
    assert "theological decree" in result.reason.lower()


def test_unauthorized_citation_rejected(validator, sample_hadith):
    """Verify that invented or re-cited Hadith citations trigger rejection."""
    cited_text = (
        "• Focus on clean and pure intentions daily.\n"
        "• This teaching is recorded in Sahih al-Bukhari hadith number 4589.\n"
        "• Maintain humility in your endeavors."
    )
    result = validator.validate(cited_text, sample_hadith)
    assert result.is_valid is False
    assert result.error_code == "ERR_UNAUTHORIZED_CITATION"


def test_inflammatory_language_rejected(validator, sample_hadith):
    """Verify that derogatory or sectarian language triggers rejection."""
    inflammatory_text = (
        "• Strive to be sincere in faith.\n"
        "• Warn people against the deviant sect in the community.\n"
        "• Keep your actions honest and sound."
    )
    result = validator.validate(inflammatory_text, sample_hadith)
    assert result.is_valid is False
    assert result.error_code == "ERR_INFLAMMATORY_LANGUAGE"


def test_hadith_text_verbatim_leakage_rejected(validator, sample_hadith):
    """Verify that copying 8+ consecutive words from the Hadith triggers leakage rejection."""
    leakage_text = (
        "• Always remember that actions are judged by motives, so each man will have what he intended.\n"
        "• Act with sincerity and patience in all affairs."
    )
    result = validator.validate(leakage_text, sample_hadith)
    assert result.is_valid is False
    assert result.error_code == "ERR_HADITH_TEXT_LEAKAGE"


def test_convenience_validate_reflection_helper(sample_hadith):
    """Verify module-level validate_reflection convenience helper."""
    valid_text = (
        "- Keep your focus on sincere effort.\n"
        "- Small honest contributions make meaningful differences over time."
    )
    result = validate_reflection(valid_text, sample_hadith)
    assert result.is_valid is True
    assert result.status == "PASSED"
