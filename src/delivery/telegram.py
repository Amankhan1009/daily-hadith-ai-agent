"""
Outbound Telegram Bot API Adapter.

Encapsulates typed HTTP communication with Telegram Bot API, including
exponential backoff, rate limit handling (429 Retry-After), HTTP 403 bot-blocked
detection, and webhook administration.
"""

import logging
import time
from typing import Any, Optional

import httpx

from src.config import get_settings

logger = logging.getLogger(__name__)


class TelegramDeliveryError(Exception):
    """Base exception for Telegram delivery and API failures."""
    pass


class TelegramBotBlockedError(TelegramDeliveryError):
    """Raised when Telegram returns HTTP 403 because the user blocked the bot or deleted the chat."""

    def __init__(self, chat_id: int | str, message: str = "Bot was blocked by the user"):
        super().__init__(f"Telegram delivery failed for chat_id={chat_id}: {message}")
        self.chat_id = chat_id


class TelegramRateLimitError(TelegramDeliveryError):
    """Raised when Telegram returns HTTP 429 and rate-limit retries are exhausted."""
    pass


class TelegramNetworkError(TelegramDeliveryError):
    """Raised on network connection errors or timeouts."""
    pass


class TelegramClient:
    """
    Robust HTTP client adapter for the official Telegram Bot API.
    """

    def __init__(
        self,
        bot_token: Optional[str] = None,
        timeout_seconds: float = 10.0,
        max_retries: int = 3,
        base_url: str = "https://api.telegram.org",
        client: Optional[httpx.Client] = None,
    ):
        settings = get_settings()
        self.bot_token = bot_token or settings.telegram_bot_token
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.base_url = base_url.rstrip("/")
        self._client = client

    @property
    def api_url(self) -> str:
        """Construct the base API URL including the secret bot token."""
        if not self.bot_token:
            raise ValueError("Telegram bot token is not configured. Set TELEGRAM_BOT_TOKEN in .env.")
        return f"{self.base_url}/bot{self.bot_token}"

    def _get_client(self) -> httpx.Client:
        """Return provided client or create a new one with configured timeouts."""
        if self._client is not None:
            return self._client
        return httpx.Client(timeout=self.timeout_seconds)

    def send_message(
        self,
        chat_id: int | str,
        text: str,
        parse_mode: str = "HTML",
        disable_web_page_preview: bool = False,
    ) -> dict[str, Any]:
        """
        Deliver a text message to a specified Telegram chat.

        Args:
            chat_id: Destination Telegram user or group chat ID.
            text: UTF-8 message content (max 4096 characters).
            parse_mode: Parsing formatting style ('HTML' or 'MarkdownV2').
            disable_web_page_preview: Disables link preview generation if True.

        Returns:
            dict[str, Any]: Telegram Message object result.

        Raises:
            ValueError: If message text exceeds Telegram limit of 4096 characters.
            TelegramBotBlockedError: If recipient blocked the bot (HTTP 403).
            TelegramRateLimitError: If rate limit retries are exhausted (HTTP 429).
            TelegramDeliveryError: On other API errors.
        """
        if len(text) > 4096:
            raise ValueError(f"Message length ({len(text)}) exceeds Telegram 4096-character limit.")

        url = f"{self.api_url}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview,
        }

        client = self._get_client()
        attempts = 0
        backoff = 1.0

        while attempts < self.max_retries:
            attempts += 1
            try:
                response = client.post(url, json=payload)

                # HTTP 200: Successful delivery
                if response.status_code == 200:
                    data = response.json()
                    if data.get("ok"):
                        return data.get("result", {})
                    raise TelegramDeliveryError(f"Telegram API error: {data.get('description', 'Unknown error')}")

                # HTTP 403: Bot was blocked or chat deleted
                if response.status_code == 403:
                    desc = "Forbidden"
                    try:
                        desc = response.json().get("description", desc)
                    except Exception:
                        pass
                    raise TelegramBotBlockedError(chat_id=chat_id, message=desc)

                # HTTP 429: Too Many Requests (Rate Limited)
                if response.status_code == 429:
                    retry_after = 1.0
                    try:
                        retry_after = float(response.json().get("parameters", {}).get("retry_after", 1.0))
                    except Exception:
                        pass
                    logger.warning("Telegram rate limited (429). Waiting %s seconds before retry...", retry_after)
                    time.sleep(retry_after)
                    continue

                # HTTP 5xx: Transient server error
                if 500 <= response.status_code < 600:
                    logger.warning(
                        "Telegram server error %s (attempt %s/%s). Retrying in %ss...",
                        response.status_code,
                        attempts,
                        self.max_retries,
                        backoff,
                    )
                    time.sleep(backoff)
                    backoff *= 2.0
                    continue

                # Other HTTP 4xx errors (e.g. 400 Bad Request)
                error_desc = response.text
                try:
                    error_desc = response.json().get("description", response.text)
                except Exception:
                    pass
                raise TelegramDeliveryError(f"Telegram API rejected request ({response.status_code}): {error_desc}")

            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                logger.warning(
                    "Telegram network error (%s) on attempt %s/%s. Retrying in %ss...",
                    exc,
                    attempts,
                    self.max_retries,
                    backoff,
                )
                if attempts >= self.max_retries:
                    raise TelegramNetworkError(f"Telegram network failure after {attempts} attempts: {exc}") from exc
                time.sleep(backoff)
                backoff *= 2.0

        raise TelegramDeliveryError(f"Exhausted {self.max_retries} attempts sending message to chat {chat_id}")

    def set_webhook(
        self,
        url: str,
        secret_token: Optional[str] = None,
        drop_pending_updates: bool = False,
    ) -> dict[str, Any]:
        """Configure Telegram inbound webhook URL and secret token verification."""
        endpoint = f"{self.api_url}/setWebhook"
        payload: dict[str, Any] = {
            "url": url,
            "drop_pending_updates": drop_pending_updates,
        }
        if secret_token:
            payload["secret_token"] = secret_token

        client = self._get_client()
        response = client.post(endpoint, json=payload)
        data = response.json()
        if not data.get("ok"):
            raise TelegramDeliveryError(f"Failed to set webhook: {data.get('description', 'Unknown error')}")
        return data.get("result", {})

    def get_webhook_info(self) -> dict[str, Any]:
        """Query current webhook configuration status from Telegram."""
        endpoint = f"{self.api_url}/getWebhookInfo"
        client = self._get_client()
        response = client.get(endpoint)
        data = response.json()
        if not data.get("ok"):
            raise TelegramDeliveryError(f"Failed to get webhook info: {data.get('description', 'Unknown error')}")
        return data.get("result", {})

    def delete_webhook(self, drop_pending_updates: bool = False) -> dict[str, Any]:
        """Remove active webhook from Telegram."""
        endpoint = f"{self.api_url}/deleteWebhook"
        payload = {"drop_pending_updates": drop_pending_updates}
        client = self._get_client()
        response = client.post(endpoint, json=payload)
        data = response.json()
        if not data.get("ok"):
            raise TelegramDeliveryError(f"Failed to delete webhook: {data.get('description', 'Unknown error')}")
        return data.get("result", {})