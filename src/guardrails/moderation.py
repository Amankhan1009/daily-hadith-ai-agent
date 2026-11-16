"""
ML-Based Content Safety and Moderation Engine using Llama Guard.

Provides secondary multi-layer safety classification using Groq Cloud's free-tier
llama-guard-3-8b model, complementing deterministic theological negative constraints.
"""

import logging
from dataclasses import dataclass
from typing import Any

from groq import Groq

from src.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModerationResult:
    """Outcome of ML-based moderation classification."""

    is_safe: bool
    status: str  # "SAFE" | "UNSAFE" | "SKIPPED" | "ERROR"
    category: str | None = None
    reason: str | None = None
    model: str = "llama-guard-3-8b"


class LlamaGuardModerator:
    """
    Moderation client using Groq Cloud's Llama Guard 3 8B.
    Performs fast, free safety classification as an auxiliary defense-in-depth layer.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        client: Any | None = None,
        enabled: bool | None = None,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.groq_api_key
        self.model = model or getattr(settings, "llama_guard_model", "llama-guard-3-8b")
        self.enabled = (
            enabled if enabled is not None else getattr(settings, "enable_llama_guard", False)
        )

        if client is not None:
            self._client = client
        elif self.api_key and self.enabled:
            try:
                self._client = Groq(api_key=self.api_key)
            except Exception as exc:
                logger.warning("Failed to initialize Groq client for Llama Guard: %s", exc)
                self._client = None
        else:
            self._client = None

    def moderate(self, text: str | None) -> ModerationResult:
        """
        Classify text for safety violations using Llama Guard.

        Fails-safe: If disabled, unconfigured, or encountering an API error,
        it returns status='SKIPPED' or 'ERROR' with is_safe=True to ensure
        theological delivery is never interrupted by upstream ML downtime.
        """
        if not self.enabled or not self._client or not text or not text.strip():
            return ModerationResult(
                is_safe=True,
                status="SKIPPED",
                reason="Llama Guard moderation disabled, unconfigured, or empty input.",
                model=self.model,
            )

        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": text.strip()}],
                temperature=0.0,
                max_tokens=64,
            )
            raw_content = response.choices[0].message.content or ""
            cleaned = raw_content.strip()
            lines = cleaned.split("\n", 1)
            verdict = lines[0].strip().lower()

            if verdict == "safe":
                return ModerationResult(
                    is_safe=True,
                    status="SAFE",
                    model=self.model,
                )
            elif verdict == "unsafe":
                category = lines[1].strip() if len(lines) > 1 else "UNSPECIFIED"
                logger.warning("Llama Guard flagged content as unsafe (category: %s)", category)
                return ModerationResult(
                    is_safe=False,
                    status="UNSAFE",
                    category=category,
                    reason=f"Flagged unsafe by Llama Guard ({category})",
                    model=self.model,
                )
            else:
                logger.warning("Unexpected Llama Guard output: %s", cleaned)
                return ModerationResult(
                    is_safe=True,
                    status="SAFE",
                    reason="Non-violating classification response",
                    model=self.model,
                )
        except Exception as exc:
            logger.warning(
                "Llama Guard evaluation failed: %s. Failing-safe to maintain delivery.",
                exc,
            )
            return ModerationResult(
                is_safe=True,
                status="ERROR",
                reason=str(exc),
                model=self.model,
            )
