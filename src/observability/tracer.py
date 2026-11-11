"""
Observability and Telemetry Integration for Daily Hadith AI Agent.

Provides centralized LangSmith cloud tracing configuration, metadata tagging,
token usage accounting, and safe fallback handling across LangGraph workflows
and Groq LLM reflection synthesis.
"""

import logging
from datetime import date
from typing import Any

from src.config import get_settings

logger = logging.getLogger(__name__)


def is_tracing_enabled() -> bool:
    """Return True if LangSmith cloud tracing is actively configured and enabled."""
    settings = get_settings()
    return bool(settings.langchain_tracing_v2 and settings.langchain_api_key)


def get_workflow_run_config(
    scheduled_date: str | None = None,
    is_dry_run: bool = False,
) -> dict[str, Any]:
    """
    Construct standardized LangGraph runtime configuration with LangSmith tags and metadata.

    Args:
        scheduled_date: Target delivery date in YYYY-MM-DD format (defaults to current date).
        is_dry_run: Whether the workflow is executing in simulated dry-run mode.

    Returns:
        dict[str, Any]: Config dictionary suitable for `graph.invoke(..., config=run_config)`.
    """
    settings = get_settings()
    date_str = scheduled_date or str(date.today())

    return {
        "run_name": f"Daily Broadcast: {date_str}",
        "tags": [
            "daily-hadith",
            settings.app_env,
            "dry_run" if is_dry_run else "live",
        ],
        "metadata": {
            "scheduled_date": date_str,
            "is_dry_run": is_dry_run,
            "app_env": settings.app_env,
            "timezone": settings.timezone,
            "groq_model": settings.groq_model,
        },
    }


def record_llm_metrics(
    response: Any,
    model_name: str,
    provider: str = "groq",
) -> None:
    """
    Safely capture token consumption and inference metadata on the active LangSmith span.

    Args:
        response: Raw completion response object from the LLM client (e.g. Groq ChatCompletion).
        model_name: Identifier of the language model invoked.
        provider: Provider name (e.g., 'groq').
    """
    if not is_tracing_enabled():
        return

    try:
        from langsmith.run_helpers import get_current_run_tree

        run_tree = get_current_run_tree()
        if not run_tree:
            return

        metadata: dict[str, Any] = {
            "ls_provider": provider,
            "ls_model_name": model_name,
        }

        usage = getattr(response, "usage", None)
        if usage:
            prompt_tokens = getattr(usage, "prompt_tokens", None)
            completion_tokens = getattr(usage, "completion_tokens", None)
            total_tokens = getattr(usage, "total_tokens", None)

            if prompt_tokens is not None:
                metadata["prompt_tokens"] = prompt_tokens
            if completion_tokens is not None:
                metadata["completion_tokens"] = completion_tokens
            if total_tokens is not None:
                metadata["total_tokens"] = total_tokens

        run_tree.add_metadata(metadata)
    except Exception as exc:  # pragma: no cover
        logger.debug("Failed to record LLM metrics to LangSmith run tree: %s", exc)
