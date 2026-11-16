"""
Pytest global fixtures and environment configuration.
"""

import os

import pytest

# Ensure unit tests do not attempt outbound LangSmith cloud tracing
os.environ["LANGCHAIN_TRACING_V2"] = "false"


@pytest.fixture(autouse=True)
def default_test_env(monkeypatch):
    """Ensure clean environment state across test invocations."""
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.setenv("ENABLE_RATE_LIMITING", "false")
    from src.config import get_settings

    get_settings.cache_clear()
    from src.security import limiter

    limiter.enabled = False
    limiter.reset()
