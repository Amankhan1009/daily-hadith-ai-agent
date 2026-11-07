"""
Automated Contract and Content Validation Tests for Notification Formatter.
"""

import pytest

from src.formatter import (
    TELEGRAM_MAX_MESSAGE_LENGTH,
    escape_html,
    format_daily_hadith_message,
)


def test_format_message_with_clean_reflection():
    """Verify that a compliant payload formats with full metadata and segregated AI disclaimer."""
    payload = format_daily_hadith_message(
        english_text="Actions are judged by motives, so each man will have what he intended.",
        attribution="Narrated by Al-Bukhari",
        collection="Sahih al-Bukhari",
        hadith_number="1",
        grade="Authentic",
        source_url="https://hadeethenc.com/en/browse/hadith/1",
        ai_reflection="• Focus on clean and pure intentions daily.",
        ai_reflection_status="PASSED_GUARDRAILS",
    )

    assert payload.parse_mode == "HTML"
    assert payload.has_reflection is True
    assert payload.character_count < TELEGRAM_MAX_MESSAGE_LENGTH

    # Verify canonical header & attribution
    assert "📖 <b>Hadith of the Day</b>" in payload.text
    assert "Actions are judged by motives" in payload.text
    assert "— <i>Narrated by Al-Bukhari</i>" in payload.text
    assert "Sahih al-Bukhari (#1)" in payload.text
    assert "🏅 <b>Grade:</b> Authentic" in payload.text
    assert 'href="https://hadeethenc.com/en/browse/hadith/1"' in payload.text

    # Verify AI commentary segregation and non-canonical disclaimer
    assert "💡 <b>Reflection & Practical Context:</b>" in payload.text
    assert (
        "(AI-generated educational commentary — not part of the original Hadith text)"
        in payload.text
    )
    assert "• Focus on clean and pure intentions daily." in payload.text


def test_format_message_without_reflection():
    """Verify clean rendering when AI reflection is omitted (e.g. guardrail drop or API failure)."""
    payload = format_daily_hadith_message(
        english_text="Actions are judged by motives...",
        attribution="Narrated by Al-Bukhari",
        collection="Sahih al-Bukhari",
        hadith_number="1",
        grade="Authentic",
        source_url="https://hadeethenc.com/en/browse/hadith/1",
        ai_reflection=None,
        ai_reflection_status="OMITTED_GUARDRAIL_FAILED",
    )

    assert payload.has_reflection is False
    assert "Reflection & Practical Context" not in payload.text
    assert "AI-generated" not in payload.text
    assert "Actions are judged by motives" in payload.text


def test_html_escaping_prevents_telegram_formatting_breakage():
    """Verify that special HTML characters (<, >, &) are escaped cleanly."""
    raw_text = "Truth guides to righteousness <virtue> & peace > chaos."
    escaped = escape_html(raw_text)
    assert "<virtue>" not in escaped
    assert "&lt;virtue&gt;" in escaped
    assert "&amp;" in escaped

    payload = format_daily_hadith_message(
        english_text=raw_text,
        attribution="Umar & Abu Bakr",
        collection="Sahih al-Bukhari",
        hadith_number="5",
        grade="Authentic",
        source_url="https://hadeethenc.com/en/browse/hadith/5",
    )
    assert "&lt;virtue&gt;" in payload.text
    assert "Umar &amp; Abu Bakr" in payload.text


def test_oversized_payload_raises_value_error():
    """Verify that payloads exceeding the Telegram 4096 character boundary are rejected fail-closed."""
    massive_text = "A" * (TELEGRAM_MAX_MESSAGE_LENGTH + 100)

    with pytest.raises(ValueError, match="exceeds Telegram limit"):
        format_daily_hadith_message(
            english_text=massive_text,
            attribution="Narrator",
            collection="Collection",
            hadith_number="100",
            grade="Authentic",
            source_url="https://hadeethenc.com",
        )
