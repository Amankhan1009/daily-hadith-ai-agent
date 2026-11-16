"""
Enterprise Application Security & Rate Limiting Engine.

Configures SlowAPI in-memory IP rate limiting, client IP extraction,
and security defense-in-depth policies for all exposed HTTP endpoints.
"""

import logging

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.config import get_settings

logger = logging.getLogger(__name__)


def get_client_ip(request: Request) -> str:
    """
    Extract client IP address for rate limiting, respecting reverse proxy headers.
    Falls back to standard SlowAPI get_remote_address.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # First entry in X-Forwarded-For is the true originating client IP
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


# Singleton Limiter instance
limiter = Limiter(
    key_func=get_client_ip,
    default_limits=[get_settings().rate_limit_default],
    enabled=get_settings().enable_rate_limiting,
)
