"""
Automated Unit Tests for Groq LLM Reflection Client and Prompt Construction.
"""

from unittest.mock import MagicMock
import pytest
from groq import Groq

from src.llm import GroqReflectionClient, build_reflection_prompt
from src.llm.prompts import REFLECTION_SYSTEM_PROMPT


def test_build_reflection_prompt_content_and_rules():
    """Verify system prompt negative constraints and user payload formatting."""
    hadith_text = "Actions are judged by intentions..."
    attribution = "Narrated by Al-Bukhari"
    collection = "Sahih al-Bukhari (#1)"

    messages = build_reflection_prompt(
        english_text=hadith_text,
        attribution=attribution,
        collection=collection,
    )

    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"

    # Verify theological safety negative constraints in system prompt
    sys_content = messages[0]["content"]
    assert "NEVER re-translate" in sys_content
    assert "NEVER issue legal rulings (Fatwas)" in sys_content
    assert "NEVER fabricate historical context" in sys_content
    assert "120 words" in sys_content

    # Verify user message structure
    user_content = messages[1]["content"]
    assert hadith_text in user_content
    assert attribution in user_content
    assert collection in user_content


def test_groq_client_omitted_when_no_api_key(monkeypatch):
    """Verify that GroqReflectionClient safely returns OMITTED when no API key is provided."""
    client = GroqReflectionClient(api_key=None, client=None)
    client._client = None  # Force unconfigured state

    result = client.generate_reflection(
        english_text="Actions are judged by intentions...",
        attribution="Narrated by Al-Bukhari",
        collection="Sahih al-Bukhari (#1)",
    )

    assert result.status == "OMITTED"
    assert result.reflection is None
    assert result.error == "GROQ_API_KEY_NOT_CONFIGURED"


def test_groq_client_generates_reflection_success_mock():
    """Verify successful reflection generation when Groq returns completion."""
    mock_groq = MagicMock(spec=Groq)

    # Mock response object structure
    mock_choice = MagicMock()
    mock_choice.message.content = (
        "• Sincerity in intention elevates everyday actions into worship.\n"
        "• Regular self-reflection ensures our goals remain spiritually grounded."
    )
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_groq.chat.completions.create.return_value = mock_response

    client = GroqReflectionClient(api_key="gsk_test", client=mock_groq)
    result = client.generate_reflection(
        english_text="Actions are judged by intentions...",
        attribution="Narrated by Al-Bukhari",
        collection="Sahih al-Bukhari (#1)",
    )

    assert result.status == "GENERATED"
    assert result.reflection is not None
    assert "Sincerity in intention" in result.reflection
    assert result.error is None


def test_groq_client_handles_api_exception_fallback():
    """Verify that API exceptions (e.g. Rate Limit 429 / Outage) gracefully fall back to FAILED without crashing."""
    mock_groq = MagicMock(spec=Groq)
    mock_groq.chat.completions.create.side_effect = RuntimeError(
        "Groq Cloud 429: Rate Limit Exceeded"
    )

    client = GroqReflectionClient(api_key="gsk_test", client=mock_groq)
    result = client.generate_reflection(
        english_text="Actions are judged by intentions...",
        attribution="Narrated by Al-Bukhari",
        collection="Sahih al-Bukhari (#1)",
    )

    assert result.status == "FAILED"
    assert result.reflection is None
    assert "Rate Limit Exceeded" in (result.error or "")


def test_groq_client_handles_empty_completion():
    """Verify that an empty response from LLM is marked FAILED without raising an error."""
    mock_groq = MagicMock(spec=Groq)
    mock_choice = MagicMock()
    mock_choice.message.content = "   "
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_groq.chat.completions.create.return_value = mock_response

    client = GroqReflectionClient(api_key="gsk_test", client=mock_groq)
    result = client.generate_reflection(
        english_text="Actions are judged by intentions...",
        attribution="Narrated by Al-Bukhari",
        collection="Sahih al-Bukhari (#1)",
    )

    assert result.status == "FAILED"
    assert result.reflection is None
    assert result.error == "EMPTY_COMPLETION_RESPONSE"