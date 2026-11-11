"""
Unit tests for Observability and LangSmith telemetry integration.
"""

from unittest.mock import MagicMock, patch

from src.config import get_settings
from src.observability.cli import run_diagnostics
from src.observability.tracer import (
    get_workflow_run_config,
    is_tracing_enabled,
    record_llm_metrics,
)


def test_is_tracing_enabled(monkeypatch):
    """Verify is_tracing_enabled correctly evaluates configuration flags."""
    get_settings.cache_clear()
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
    get_settings.cache_clear()
    assert is_tracing_enabled() is False

    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monkeypatch.setenv("LANGCHAIN_API_KEY", "lsv2_pt_test_key_12345")
    get_settings.cache_clear()
    assert is_tracing_enabled() is True
    get_settings.cache_clear()


def test_get_workflow_run_config(monkeypatch):
    """Verify run configuration metadata and tags generation for LangGraph."""
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("GROQ_MODEL", "openai/gpt-oss-120b")
    get_settings.cache_clear()

    config = get_workflow_run_config(scheduled_date="2026-11-15", is_dry_run=True)

    assert config["run_name"] == "Daily Broadcast: 2026-11-15"
    assert "daily-hadith" in config["tags"]
    assert "dry_run" in config["tags"]
    assert "staging" in config["tags"]

    metadata = config["metadata"]
    assert metadata["scheduled_date"] == "2026-11-15"
    assert metadata["is_dry_run"] is True
    assert metadata["app_env"] == "staging"
    assert metadata["groq_model"] == "openai/gpt-oss-120b"
    get_settings.cache_clear()


def test_record_llm_metrics_when_disabled(monkeypatch):
    """Calling record_llm_metrics when tracing is disabled should be a safe no-op."""
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    get_settings.cache_clear()

    mock_response = MagicMock()
    # Should not raise exception
    record_llm_metrics(response=mock_response, model_name="test-model")
    get_settings.cache_clear()


def test_record_llm_metrics_active(monkeypatch):
    """Calling record_llm_metrics with active tracing should inject metadata into RunTree."""
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monkeypatch.setenv("LANGCHAIN_API_KEY", "lsv2_pt_test_key_12345")
    get_settings.cache_clear()

    mock_run_tree = MagicMock()
    mock_response = MagicMock()
    mock_response.usage.prompt_tokens = 120
    mock_response.usage.completion_tokens = 45
    mock_response.usage.total_tokens = 165

    with patch("langsmith.run_helpers.get_current_run_tree", return_value=mock_run_tree):
        record_llm_metrics(
            response=mock_response, model_name="openai/gpt-oss-120b", provider="groq"
        )

    mock_run_tree.add_metadata.assert_called_once()
    called_metadata = mock_run_tree.add_metadata.call_args[0][0]
    assert called_metadata["ls_provider"] == "groq"
    assert called_metadata["ls_model_name"] == "openai/gpt-oss-120b"
    assert called_metadata["prompt_tokens"] == 120
    assert called_metadata["completion_tokens"] == 45
    assert called_metadata["total_tokens"] == 165
    get_settings.cache_clear()


def test_cli_diagnostics_disabled(capsys, monkeypatch):
    """CLI diagnostics should output clean inspection status when tracing is disabled."""
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)

    exit_code = run_diagnostics(verbose=False)
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "OBSERVABILITY & TRACING DIAGNOSTICS" in captured.out
    assert "LangSmith tracing is currently disabled" in captured.out
