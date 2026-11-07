"""
Resilient Groq LLM Client for Hadith Reflection Generation.

Provides structured completion handling, configurable model parameters,
and automatic fail-safe fallback when API keys are missing or services outage.
"""

import logging
from dataclasses import dataclass

from groq import Groq

from src.config import get_settings
from src.llm.prompts import build_reflection_prompt

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReflectionResult:
    """Structured outcome of an LLM reflection generation attempt."""

    reflection: str | None
    status: str  # "GENERATED" | "OMITTED" | "FAILED"
    model: str
    error: str | None = None


class GroqReflectionClient:
    """
    Client interface for generating segregated Hadith reflections via Groq Cloud.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        client: Groq | None = None,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.groq_api_key
        self.model = model or settings.groq_model
        self.temperature = settings.groq_temperature
        self.max_tokens = settings.groq_max_tokens

        if client is not None:
            self._client = client
        elif self.api_key:
            self._client = Groq(api_key=self.api_key)
        else:
            self._client = None

    def generate_reflection(
        self,
        english_text: str,
        attribution: str,
        collection: str,
    ) -> ReflectionResult:
        """
        Generate a concise, practical ethical reflection for a verified Hadith.
        If no API key is configured or the request fails, returns a safe fallback.
        """
        if self._client is None:
            logger.info("Groq API key not configured. Omitting AI reflection safely.")
            return ReflectionResult(
                reflection=None,
                status="OMITTED",
                model=self.model,
                error="GROQ_API_KEY_NOT_CONFIGURED",
            )

        messages = build_reflection_prompt(
            english_text=english_text,
            attribution=attribution,
            collection=collection,
        )

        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,  # type: ignore
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            raw_text = response.choices[0].message.content or ""
            cleaned = raw_text.strip()

            if not cleaned:
                return ReflectionResult(
                    reflection=None,
                    status="FAILED",
                    model=self.model,
                    error="EMPTY_COMPLETION_RESPONSE",
                )

            return ReflectionResult(
                reflection=cleaned,
                status="GENERATED",
                model=self.model,
                error=None,
            )
        except Exception as exc:
            logger.warning(
                "Groq reflection generation failed: %s. Falling back to omission.",
                exc,
            )
            return ReflectionResult(
                reflection=None,
                status="FAILED",
                model=self.model,
                error=str(exc),
            )
