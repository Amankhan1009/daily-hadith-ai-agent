"""
Unit tests for application configuration and settings.
"""

import pytest
from pydantic import ValidationError

from src.config import Settings


def test_default_settings():
    """Verify default configuration values align with production requirements."""
    settings = Settings()

    assert settings.app_env == "development"
    assert settings.timezone == "Asia/Kolkata"
    assert settings.schedule_cron == "0 10 * * *"
    assert settings.hadeethenc_base_url == "https://hadeethenc.com/api/v1"
    assert settings.hadeethenc_timeout_seconds == 10.0
    assert settings.hadeethenc_max_retries == 3
    assert settings.groq_model == "openai/gpt-oss-120b"
    assert settings.is_production() is False


def test_valid_timezone_validation():
    """Valid IANA timezones should pass validation."""
    settings = Settings(timezone="UTC")
    assert settings.timezone == "UTC"

    settings_kolkata = Settings(timezone="Asia/Kolkata")
    assert settings_kolkata.timezone == "Asia/Kolkata"


def test_invalid_timezone_raises_error():
    """An invalid timezone string must fail fast with a ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(timezone="Mars/Olympus_Mons")
    assert "Invalid IANA timezone" in str(exc_info.value)


def test_numeric_boundary_validation():
    """Negative timeouts or invalid temperatures must fail validation."""
    with pytest.raises(ValidationError):
        Settings(hadeethenc_timeout_seconds=-1.0)

    with pytest.raises(ValidationError):
        Settings(groq_temperature=1.5)


def test_safe_summary_masks_secrets():
    """Verify get_safe_summary never exposes raw secret credentials."""
    settings = Settings(
        telegram_bot_token="123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
        telegram_chat_id="987654321",
        groq_api_key="gsk_1234567890abcdef1234567890abcdef",
    )

    summary = settings.get_safe_summary()

    # Raw tokens must NOT be in summary
    assert "123456789:ABCdefGHIjklMNOpqrsTUVwxyz" not in str(summary)
    assert "gsk_1234567890abcdef1234567890abcdef" not in str(summary)
    assert "987654321" not in str(summary)

    # Boolean flags should be set
    assert summary["telegram_configured"] is True
    assert summary["groq_configured"] is True


def test_environment_override(monkeypatch):
    """Environment variables must override default settings."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    monkeypatch.setenv("HADEETHENC_TIMEOUT_SECONDS", "15.5")

    settings = Settings()
    assert settings.app_env == "production"
    assert settings.is_production() is True
    assert settings.log_level == "WARNING"
    assert settings.hadeethenc_timeout_seconds == 15.5
