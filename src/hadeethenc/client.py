"""
HTTP Client for the official HadeethEnc REST API.

Provides typed methods for candidate discovery, dual English/Arabic retrieval,
strict timeout enforcement, and domain-specific error mapping.
"""

from typing import Any, Optional
import httpx
from pydantic import ValidationError

from src.config import get_settings
from src.hadeethenc.schemas import (
    HadeethEncArabicDetail,
    HadeethEncCandidatePair,
    HadeethEncEnglishDetail,
    HadeethEncListResponse,
)


class HadeethEncError(Exception):
    """Base exception for all HadeethEnc integration errors."""

    pass


class HadeethEncNotFoundError(HadeethEncError):
    """Raised when a requested Hadith record ID does not exist."""

    pass


class HadeethEncNetworkError(HadeethEncError):
    """Raised on connection failures, DNS errors, or network timeouts."""

    pass


class HadeethEncResponseError(HadeethEncError):
    """Raised when the API returns an unexpected status code or malformed payload."""

    pass


class HadeethEncClient:
    """
    Client for interacting with HadeethEnc REST API endpoints.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        client: Optional[httpx.Client] = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.hadeethenc_base_url).rstrip("/")
        self.timeout = timeout_seconds or settings.hadeethenc_timeout_seconds

        # Allow injecting a pre-configured httpx.Client (e.g., for testing with mock transports)
        self._client = client or httpx.Client(
            timeout=self.timeout,
            headers={"User-Agent": "DailyHadithAgent/1.0 (Production-Oriented AI Project)"},
        )
        self._owns_client = client is None

    def __enter__(self) -> "HadeethEncClient":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP client session."""
        if self._owns_client:
            self._client.close()

    @staticmethod
    def build_canonical_url(source_id: str | int) -> str:
        """Construct the canonical web browse URL for a HadeethEnc record."""
        return f"https://hadeethenc.com/en/browse/hadith/{source_id}"

    def _get(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute a GET request with unified error mapping."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            response = self._client.get(url, params=params)
        except httpx.TimeoutException as exc:
            raise HadeethEncNetworkError(
                f"Request to {url} timed out after {self.timeout}s."
            ) from exc
        except httpx.NetworkError as exc:
            raise HadeethEncNetworkError(
                f"Network failure while requesting {url}: {exc}"
            ) from exc

        if response.status_code == 404:
            raise HadeethEncNotFoundError(f"Record not found at {url} with params {params}")

        if response.status_code != 200:
            raise HadeethEncResponseError(
                f"HadeethEnc returned HTTP {response.status_code}: {response.text[:200]}"
            )

        try:
            data = response.json()
        except Exception as exc:
            raise HadeethEncResponseError(f"Failed to decode JSON response from {url}") from exc

        # HadeethEnc returns an empty string or empty body on some invalid IDs
        if data == "" or data is None:
            raise HadeethEncNotFoundError(f"Record not found (empty response) for params {params}")

        return data

    def get_hadiths_by_category(
        self,
        category_id: int | str = 1,
        page: int = 1,
        per_page: int = 20,
        language: str = "en",
    ) -> HadeethEncListResponse:
        """Fetch a paginated list of Hadith summaries for a specific category."""
        data = self._get(
            endpoint="hadeeths/list/",
            params={
                "language": language,
                "category_id": str(category_id),
                "page": str(page),
                "per_page": str(per_page),
            },
        )
        try:
            return HadeethEncListResponse.model_validate(data)
        except ValidationError as exc:
            raise HadeethEncResponseError(f"Malformed list response: {exc}") from exc

    def get_english_hadith(self, hadith_id: str | int) -> HadeethEncEnglishDetail:
        """Fetch full details for a single English Hadith record."""
        data = self._get(
            endpoint="hadeeths/one/",
            params={"language": "en", "id": str(hadith_id)},
        )
        try:
            return HadeethEncEnglishDetail.model_validate(data)
        except ValidationError as exc:
            raise HadeethEncResponseError(
                f"Malformed English payload for ID {hadith_id}: {exc}"
            ) from exc

    def get_arabic_hadith(self, hadith_id: str | int) -> HadeethEncArabicDetail:
        """Fetch full details for the Arabic counterpart record."""
        data = self._get(
            endpoint="hadeeths/one/",
            params={"language": "ar", "id": str(hadith_id)},
        )
        try:
            return HadeethEncArabicDetail.model_validate(data)
        except ValidationError as exc:
            raise HadeethEncResponseError(
                f"Malformed Arabic payload for ID {hadith_id}: {exc}"
            ) from exc

    def get_candidate_pair(self, hadith_id: str | int) -> HadeethEncCandidatePair:
        """
        Fetch both English and Arabic records for a Hadith ID and return a correlated pair.
        """
        str_id = str(hadith_id)
        english = self.get_english_hadith(str_id)
        arabic = self.get_arabic_hadith(str_id)
        canonical_url = self.build_canonical_url(str_id)

        return HadeethEncCandidatePair(
            source_id=str_id,
            english=english,
            arabic=arabic,
            canonical_url=canonical_url,
        )