# Automated Test Suite (`tests/`)

This directory contains the automated unit and integration tests for the **Daily Hadith AI Agent**.

The test suite enforces a strict **sub-second execution standard** by utilizing in-memory SQLite fixtures (`sqlite:///:memory:`) and mocked HTTP transports (`httpx.MockTransport`), guaranteeing zero cloud database pollution and deterministic reproducibility.

---

## Test Modules Overview

| Test Module | Component Tested | Test Count | Key Invariants Verified |
|---|---|---|---|
| **[`test_config.py`](test_config.py)** | `src.config` | 6 tests | IANA timezone validation (`Asia/Kolkata`), numeric boundaries, secret masking in logs, env overrides. |
| **[`test_database.py`](test_database.py)** | `src.database` | 8 tests | Candidate persistence, updating records, subscriber lifecycle, idempotent `/start`, active subscriber filtering, unique date constraint. |
| **[`test_delivery.py`](test_delivery.py)** | `src.delivery` | 9 tests | TelegramClient sendMessage mock, 4096 character limits, HTTP 403 bot blocked handling, HTTP 429 rate limit retries, webhook secret token validation, `/start`, `/stop`, `/help` routing. |
| **[`test_failure_handling.py`](test_failure_handling.py)** | `src.hadeethenc`, `src.llm`, `src.delivery`, `src.database` | 19 tests | Upstream HadeethEnc 500/timeout/malformed payload fail-closed, Groq keyless omission & rate limit fallback, Telegram transient 500 backoff retries, mixed fan-out subscriber isolation (delivered/blocked/failed), forged webhook 403, database unique date and composite constraints. |
| **[`test_formatter.py`](test_formatter.py)** | `src.formatter` | 4 tests | Telegram HTML payload formatting, quote preservation, HTML entity escaping, 4096 character limits. |
| **[`test_guardrails.py`](test_guardrails.py)** | `src.guardrails` | 10 tests | Fatwa prohibitions, unauthorized citations, text leakage detection, length limits, bullet formatting. |
| **[`test_hadeethenc.py`](test_hadeethenc.py)** | `src.hadeethenc` | 14 tests | API client mocking, 404/500/timeout handling, Arabic text identity, regex citation extraction, bibliographic rejection. |
| **[`test_idempotency.py`](test_idempotency.py)** | `src.database`, `src.workflow` | 3 tests | Composite unique constraint `(subscriber_id, scheduled_date)` violation handling, mid-run crash recovery skipping delivered users, zero messages sent on complete rerun. |
| **[`test_ingestion.py`](test_ingestion.py)** | `src.ingestion` | 4 tests | Verified candidate persistence, rejected audit recording, deduplication idempotency, batch metrics calculation. |
| **[`test_llm.py`](test_llm.py)** | `src.llm` | 5 tests | Negative constraint prompt rules, omitted key fallback, mock completion, API error resilience. |
| **[`test_scheduler.py`](test_scheduler.py)** | `src.workflow`, `src.main` | 4 tests | Daily runner dry-run execution, APScheduler Asia/Kolkata timezone and 1-hour misfire grace time, container health check, authenticated Cloud Scheduler cron trigger. |
| **[`test_workflow.py`](test_workflow.py)** | `src.workflow` | 8 tests | LangGraph StateGraph happy path, idempotency skip routing, queue empty abort, safety abort, guardrail fail-safe omission, clean reflection pass, multi-user fan-out and HTTP 403 auto-deactivation. |
| **Total** | **All Modules** | **94 tests** | **100% automated pass rate** |

---

## Running the Tests & Quality Audits

### Run All Tests with Coverage Report:
```bash
.venv/bin/pytest --cov=src --cov-report=term-missing -v
```

### Run a Specific Module:
```bash
.venv/bin/pytest tests/test_workflow.py -v
```

### Run Ruff Linter & Formatter:
```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```
