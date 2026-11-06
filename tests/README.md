# Automated Test Suite (`tests/`)

This directory contains the automated unit and integration tests for the **Daily Hadith AI Agent**.

The test suite enforces a strict **sub-second execution standard** by utilizing in-memory SQLite fixtures (`sqlite:///:memory:`) and mocked HTTP transports (`httpx.MockTransport`), guaranteeing zero cloud database pollution and deterministic reproducibility.

---

## Test Modules Overview

| Test Module | Component Tested | Test Count | Key Invariants Verified |
|---|---|---|---|
| **[`test_config.py`](test_config.py)** | `src.config` | 6 tests | IANA timezone validation (`Asia/Kolkata`), numeric boundaries, secret masking in logs, env overrides. |
| **[`test_database.py`](test_database.py)** | `src.database` | 5 tests | Candidate persistence, updating records, daily delivery idempotency, unique date constraint. |
| **[`test_hadeethenc.py`](test_hadeethenc.py)** | `src.hadeethenc` | 15 tests | API client mocking, 404/500/timeout handling, Arabic text identity, regex citation extraction, bibliographic rejection. |
| **[`test_ingestion.py`](test_ingestion.py)** | `src.ingestion` | 4 tests | Verified candidate persistence, rejected audit recording, deduplication idempotency, batch metrics calculation. |
| **[`test_llm.py`](test_llm.py)** | `src.llm` | 5 tests | Negative constraint prompt rules, omitted key fallback, mock completion, API error resilience. |
| **[`test_guardrails.py`](test_guardrails.py)** | `src.guardrails` | 10 tests | Fatwa prohibitions, unauthorized citations, text leakage detection, length limits, bullet formatting. |
| **[`test_formatter.py`](test_formatter.py)** | `src.formatter` | 4 tests | Telegram HTML payload formatting, quote preservation, HTML entity escaping, 4096 character limits. |
| **[`test_workflow.py`](test_workflow.py)** | `src.workflow` | 6 tests | LangGraph StateGraph happy path, idempotency skip routing, queue empty abort, safety abort, guardrail fail-safe omission. |
| **Total** | **All Modules** | **55 tests** | **100% automated pass rate in <1.6s** |

---

## Running the Tests

Run all tests:
```bash
.venv/bin/pytest -v
```

Run a specific module:
```bash
.venv/bin/pytest tests/test_workflow.py -v
```