"""
Canonical Notification Payload Formatter.

Assembles compliant, strictly verified notification payloads for Telegram delivery,
enforcing source text invariance, attribution integrity, character limits,
and explicit segregation of non-canonical AI reflections.
"""

from dataclasses import dataclass
import html
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Telegram message length limit
TELEGRAM_MAX_MESSAGE_LENGTH: int = 4096


@dataclass(frozen=True)
class NotificationPayload:
    """Structured, verified notification ready for delivery dispatch."""

    text: str
    parse_mode: str  # "HTML"
    character_count: int
    has_reflection: bool


def escape_html(text: Optional[str]) -> str:
    """
    Escape HTML special characters for Telegram HTML parse mode.
    Only <, >, and & require escaping; quotes (' and ") are preserved for clean readability.
    """
    if not text:
        return ""
    return html.escape(text.strip(), quote=False)


def format_daily_hadith_message(
    english_text: str,
    attribution: str,
    collection: str,
    hadith_number: str,
    grade: str,
    source_url: str,
    ai_reflection: Optional[str] = None,
    ai_reflection_status: Optional[str] = None,
) -> NotificationPayload:
    """
    Assemble the canonical notification payload using clean Telegram HTML formatting.
    """
    clean_text = english_text.strip()
    clean_attr = attribution.strip()
    clean_coll = collection.strip()
    clean_num = str(hadith_number).strip()
    clean_grade = grade.strip() or "Authentic"
    clean_url = source_url.strip()

    # Build core canonical sections (Immutable Sacred Material)
    lines: list[str] = [
        "📖 <b>Hadith of the Day</b>",
        "",
        f'"{escape_html(clean_text)}"',
        "",
        f"— <i>{escape_html(clean_attr)}</i>",
        f"📚 <b>Collection:</b> {escape_html(clean_coll)} (#{escape_html(clean_num)})",
        f"🏅 <b>Grade:</b> {escape_html(clean_grade)}",
        "",
        f'🔗 <b>Canonical Source:</b> <a href="{clean_url}">{escape_html(clean_url)}</a>',
    ]

    has_reflection = False
    # Append strictly segregated AI commentary if validated
    if ai_reflection and ai_reflection_status in ("GENERATED", "PASSED_GUARDRAILS"):
        clean_reflection = ai_reflection.strip()
        if clean_reflection:
            has_reflection = True
            lines.extend([
                "",
                "💡 <b>Reflection & Practical Context:</b>",
                f"<i>(AI-generated educational commentary — not part of the original Hadith text)</i>",
                "",
                escape_html(clean_reflection),
            ])

    assembled = "\n".join(lines)

    # Invariant: Must not exceed Telegram message boundary
    if len(assembled) > TELEGRAM_MAX_MESSAGE_LENGTH:
        raise ValueError(
            f"Assembled message exceeds Telegram limit ({len(assembled)} > {TELEGRAM_MAX_MESSAGE_LENGTH} chars)."
        )

    return NotificationPayload(
        text=assembled,
        parse_mode="HTML",
        character_count=len(assembled),
        has_reflection=has_reflection,
    )