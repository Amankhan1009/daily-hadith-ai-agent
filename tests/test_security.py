"""
Enterprise Security, Rate Limiting & Multi-Layer Moderation Test Suite.

Verifies:
1. Client IP address extraction from X-Forwarded-For proxy headers.
2. SlowAPI in-memory rate limiting enforcement and 429 Too Many Requests responses.
3. Dynamic rate limit bypassing when disabled via configuration.
4. Llama Guard 3 secondary ML moderation classification (Safe, Unsafe, Skipped, Error).
5. Resilient fail-safe behavior when ML services experience exceptions.
6. Integration between ReflectionValidator and LlamaGuardModerator.
7. Automated pip-audit vulnerability validation (Zero CVE invariant).
"""

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from src.guardrails.moderation import LlamaGuardModerator, ModerationResult
from src.guardrails.validator import ReflectionValidator
from src.security import get_client_ip


def test_get_client_ip_with_x_forwarded_for():
    """Verify true client IP is extracted from multi-hop X-Forwarded-For headers."""
    # Build mock request with X-Forwarded-For
    scope = {
        "type": "http",
        "headers": [(b"x-forwarded-for", b"203.0.113.195, 70.41.3.18, 150.172.238.178")],
    }
    request = Request(scope=scope)
    ip = get_client_ip(request)
    assert ip == "203.0.113.195"


def test_get_client_ip_fallback():
    """Verify client IP extraction falls back cleanly when X-Forwarded-For is absent."""
    scope = {
        "type": "http",
        "client": ("192.168.1.100", 54321),
        "headers": [],
    }
    request = Request(scope=scope)
    ip = get_client_ip(request)
    assert ip == "192.168.1.100"


def test_rate_limiter_enforces_limit_and_returns_429():
    """Verify SlowAPI throttles abusive traffic with 429 Too Many Requests."""
    test_limiter = Limiter(
        key_func=lambda request: "test_ip_123", default_limits=["3/minute"], enabled=True
    )
    test_app = FastAPI()
    test_app.state.limiter = test_limiter
    test_app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    test_app.add_middleware(SlowAPIMiddleware)

    @test_app.get("/rate-limited")
    @test_limiter.limit("3/minute")
    def sample_endpoint(request: Request):
        return {"ok": True}

    client = TestClient(test_app)

    # First 3 requests must succeed
    assert client.get("/rate-limited").status_code == 200
    assert client.get("/rate-limited").status_code == 200
    assert client.get("/rate-limited").status_code == 200

    # 4th request must be throttled with 429
    throttled = client.get("/rate-limited")
    assert throttled.status_code == 429
    assert "Rate limit exceeded" in throttled.text


def test_rate_limiter_disabled_allows_traffic():
    """Verify rate limiter does not block traffic when disabled."""
    test_limiter = Limiter(
        key_func=lambda request: "test_ip_456", default_limits=["2/minute"], enabled=False
    )
    test_app = FastAPI()
    test_app.state.limiter = test_limiter
    test_app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    test_app.add_middleware(SlowAPIMiddleware)

    @test_app.get("/bypass-route")
    @test_limiter.limit("2/minute")
    def sample_endpoint(request: Request):
        return {"ok": True}

    client = TestClient(test_app)

    for _ in range(5):
        res = client.get("/bypass-route")
        assert res.status_code == 200


def test_llama_guard_disabled_or_empty_skips():
    """Verify moderator safely skips when unconfigured, disabled, or receiving empty input."""
    # Disabled
    moderator = LlamaGuardModerator(enabled=False)
    res = moderator.moderate("Some reflection text")
    assert res.is_safe is True
    assert res.status == "SKIPPED"

    # Empty text
    enabled_mod = LlamaGuardModerator(enabled=True, client=MagicMock())
    res_empty = enabled_mod.moderate("   ")
    assert res_empty.is_safe is True
    assert res_empty.status == "SKIPPED"


def test_llama_guard_safe_verdict():
    """Verify moderator parses 'safe' classification properly."""
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "safe"
    mock_client.chat.completions.create.return_value.choices = [mock_choice]

    moderator = LlamaGuardModerator(enabled=True, client=mock_client)
    res = moderator.moderate("A gentle reflection on patience and charity.")
    assert res.is_safe is True
    assert res.status == "SAFE"
    assert res.category is None


def test_llama_guard_unsafe_verdict():
    """Verify moderator parses 'unsafe\nS1' and flags policy violation."""
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "unsafe\nS1"
    mock_client.chat.completions.create.return_value.choices = [mock_choice]

    moderator = LlamaGuardModerator(enabled=True, client=mock_client)
    res = moderator.moderate("Inflammatory harmful text snippet.")
    assert res.is_safe is False
    assert res.status == "UNSAFE"
    assert res.category == "S1"
    assert "Flagged unsafe by Llama Guard (S1)" in res.reason


def test_llama_guard_api_error_fails_safe():
    """Verify upstream Groq API exceptions fail safe to prevent delivery interruptions."""
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = RuntimeError(
        "Groq Cloud 503 Service Unavailable"
    )

    moderator = LlamaGuardModerator(enabled=True, client=mock_client)
    res = moderator.moderate("A reflection to check under outage conditions.")
    assert res.is_safe is True
    assert res.status == "ERROR"
    assert "503 Service Unavailable" in res.reason


def test_reflection_validator_integration_with_moderator():
    """Verify ReflectionValidator integrates secondary ML moderation checks."""
    valid_reflection = (
        "This sacred guidance reminds us of continuous gratitude in daily interactions.\n\n"
        "Key practical takeaways:\n"
        "- Cultivate sincere patience in everyday relationships.\n"
        "- Seek forgiveness through humble repentance and good deeds.\n"
        "- Practice generosity with family and neighbors unconditionally."
    )

    # 1. With Safe Moderator
    safe_moderator = MagicMock()
    safe_moderator.moderate.return_value = ModerationResult(is_safe=True, status="SAFE")

    validator = ReflectionValidator(moderator=safe_moderator)
    res_passed = validator.validate(valid_reflection)
    assert res_passed.is_valid is True
    assert res_passed.status == "PASSED"

    # 2. With Unsafe Moderator
    unsafe_moderator = MagicMock()
    unsafe_moderator.moderate.return_value = ModerationResult(
        is_safe=False,
        status="UNSAFE",
        category="S2",
        reason="Violated content safety policies.",
    )

    validator_unsafe = ReflectionValidator(moderator=unsafe_moderator)
    res_rejected = validator_unsafe.validate(valid_reflection)
    assert res_rejected.is_valid is False
    assert res_rejected.status == "REJECTED"
    assert res_rejected.error_code == "ERR_LLM_SAFETY_VIOLATION"


def test_pip_audit_cli_installed_and_callable():
    """Verify pip-audit is properly installed and outputs version."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "pip_audit", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    combined_output = (result.stdout or "") + (result.stderr or "")
    assert "pip-audit" in combined_output


def test_pip_audit_vulnerability_scan():
    """
    Automated check verifying that pip-audit vulnerability scanner runs
    and confirms zero known CVEs across all requirements.txt dependencies.
    Skips if running in an isolated offline sandbox environment.
    """
    import socket
    import subprocess
    import sys

    try:
        socket.getaddrinfo("pypi.org", 443)
    except socket.gaierror:
        pytest.skip("Offline / sandboxed test environment: Skipping live PyPI CVE query.")

    result = subprocess.run(
        [sys.executable, "-m", "pip_audit", "-r", "requirements.txt"],
        capture_output=True,
        text=True,
    )
    combined_output = (result.stdout or "") + (result.stderr or "")
    assert result.returncode == 0, (
        f"pip-audit found vulnerabilities:\n{result.stdout}\n{result.stderr}"
    )
    assert "No known vulnerabilities found" in combined_output
