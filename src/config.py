"""
Application Configuration and Settings Management.

Utilizes Pydantic v2 and Pydantic Settings for strictly typed,
environment-driven configuration with fail-fast validation.
"""

from functools import lru_cache
from typing import Literal, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Centralized application settings.
    Reads from environment variables and an optional .env file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application Environment & Runtime
    app_env: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Application deployment environment",
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging severity threshold",
    )
    timezone: str = Field(
        default="Asia/Kolkata",
        description="Standard execution timezone for scheduled runs",
    )
    schedule_cron: str = Field(
        default="0 10 * * *",
        description="Cron expression for daily execution (10:00 AM default)",
    )

    # HadeethEnc Source Integration
    hadeethenc_base_url: str = Field(
        default="https://hadeethenc.com/api/v1",
        description="Official REST base URL for HadeethEnc",
    )
    hadeethenc_timeout_seconds: float = Field(
        default=10.0,
        gt=0.0,
        description="HTTP client request timeout in seconds",
    )
    hadeethenc_max_retries: int = Field(
        default=3,
        ge=0,
        description="Maximum HTTP retry attempts on transient network errors",
    )

    # Telegram Delivery Credentials & Public Bot Configuration
    telegram_bot_token: Optional[str] = Field(
        default=None,
        description="Telegram bot token obtained from @BotFather",
    )
    telegram_chat_id: Optional[str] = Field(
        default=None,
        description="Optional default destination Telegram chat ID (fallback/admin)",
    )
    telegram_webhook_secret: Optional[str] = Field(
        default=None,
        description="Secret token verifying incoming webhook requests from Telegram",
    )
    telegram_bot_username: Optional[str] = Field(
        default=None,
        description="Public Telegram bot username without @ symbol (e.g. DailyHadithAiBot)",
    )

    # Groq LLM Configuration
    groq_api_key: Optional[str] = Field(
        default=None,
        description="Groq Cloud API key for reflection generation",
    )
    groq_model: str = Field(
        default="openai/gpt-oss-120b",
        description="Target Groq model identifier",
    )
    groq_temperature: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Sampling temperature for reflection generation",
    )
    groq_max_tokens: int = Field(
        default=512,
        gt=0,
        description="Maximum completion token limit",
    )

    # Database Persistence
    database_url: str = Field(
        default="sqlite:///./daily_hadith.db",
        description="Database connection string (SQLite dev / Neon PG prod)",
    )

    # Optional Auxiliary Tooling (Tavily MCP)
    tavily_api_key: Optional[str] = Field(
        default=None,
        description="Optional Tavily API key for auxiliary research",
    )

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        """Ensure the specified timezone string is a valid IANA timezone."""
        try:
            ZoneInfo(v)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Invalid IANA timezone '{v}'. Must be a valid timezone like 'Asia/Kolkata'.") from exc
        return v

    @field_validator("groq_api_key", mode="before")
    @classmethod
    def validate_groq_api_key(cls, v: Optional[str]) -> Optional[str]:
        """Ensure placeholder keys do not mask valid .env configuration."""
        if v and "your" in v.lower():
            from dotenv import dotenv_values
            env_vals = dotenv_values(".env")
            file_key = env_vals.get("GROQ_API_KEY")
            if file_key and "your" not in file_key.lower():
                return file_key
            return None
        return v

    def is_production(self) -> bool:
        """Helper to check if running in production mode."""
        return self.app_env == "production"

    @property
    def app_timezone(self) -> str:
        """Convenience alias for timezone."""
        return self.timezone

    def get_safe_summary(self) -> dict:
        """
        Returns configuration dictionary with all secret tokens masked.
        Safe for operational logging and diagnostic inspection.
        """
        def mask(val: Optional[str]) -> str:
            if not val or val.startswith("your_"):
                return "<NOT_SET>"
            if len(val) <= 8:
                return "********"
            return f"{val[:4]}...{val[-4:]}"

        return {
            "app_env": self.app_env,
            "log_level": self.log_level,
            "timezone": self.timezone,
            "schedule_cron": self.schedule_cron,
            "hadeethenc_base_url": self.hadeethenc_base_url,
            "hadeethenc_timeout_seconds": self.hadeethenc_timeout_seconds,
            "hadeethenc_max_retries": self.hadeethenc_max_retries,
            "database_url": self.database_url if not self.database_url.startswith("postgresql") else "<POSTGRES_MASKED>",
            "telegram_configured": bool(self.telegram_bot_token and self.telegram_chat_id),
            "groq_configured": bool(self.groq_api_key),
            "groq_model": self.groq_model,
            "tavily_configured": bool(self.tavily_api_key),
            "telegram_configured": bool(self.telegram_bot_token),
            "telegram_webhook_configured": bool(self.telegram_webhook_secret),
            "telegram_bot_username": self.telegram_bot_username or "<NOT_SET>",           
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached factory returning singleton application settings instance."""
    return Settings()
