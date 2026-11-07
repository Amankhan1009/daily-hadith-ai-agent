# Project Roadmap: Daily Hadith AI Agent

A tracked, production-oriented engineering roadmap for the Daily Hadith AI Agent.

---

## Status Legend
- **`Not Started`**: Scope defined, prerequisite work pending.
- **`In Progress`**: Active milestone under active implementation or review.
- **`Blocked`**: A technical or informational blocker prevents forward progress.
- **`Verified`**: Acceptance criteria fully met with recorded terminal/test evidence.

---

## Milestones Summary

| Milestone | Title | Status |
|---|---|---|
| 01 | Project Foundation and Documentation | Verified |
| 02 | Source Validation Specification | Verified |
| 03 | Configuration and Secrets | Verified |
| 04 | Database Foundation | Verified |
| 05 | HadeethEnc Integration | Verified |
| 06 | Source Catalogue Audit | Verified |
| 07 | Deterministic Validation | Verified |
| 08 | LangGraph Workflow | Verified |
| 09 | Groq Integration | Verified |
| 10 | Guardrails AI | Verified |
| 11 | Final Content Validation | Verified |
| 12 | Telegram Integration & Public Subscription Engine | Verified |
| 13 | Scheduling & Daily Multi-User Broadcast | Verified |
| 14 | History & Per-Subscriber Daily Idempotency | Verified |
| 15 | Failure Handling & System Resilience | Verified |
| 16 | Automated Testing & Code Quality Audit | Verified |
| 17 | Docker Containerization & GitHub Actions CI/CD | Verified |
| 18 | Cloud Deployment & Public Production Bot | Verified |
| 19 | Production Readiness | In Progress |
| 20 | Future FCM Support (Evaluation) | Not Started |

---

## Milestone 01 — Project Foundation and Documentation
- **Goal:** Establish a clean development environment, Git version control, core directory layout, and foundational repository documentation.
- **Scope:** Workspace inspection, Git setup, `.gitignore`, directory scaffolding (`docs/`, `src/`, `tests/`), `PROJECT_ROADMAP.md`, `PROJECT_CONTEXT.md`, and initial `README.md`. No application code.
- **Dependencies:** None.
- **Acceptance Criteria:**
  - Workspace environment (OS, shell, Python version, Git) audited and documented.
  - `.gitignore` ignores virtual environments, secrets (`.env*`), caches, logs, and database files.
  - Base directory structure established and tracked in Git.
  - Roadmap, project context, and README committed to repository.
- **Current Status:** `Verified`
- **Verification Evidence:**
  - Environment inspection confirmed: macOS 27.0.1 (arm64), zsh, Python 3.14.6, Git 2.54.0.
  - Git initialized on `main` branch.
  - `.gitignore` created and verified with `git status`.
  - Directories `docs/`, `src/`, `tests/` created with tracked `.gitkeep` markers.
  - `README.md`, `docs/PROJECT_ROADMAP.md`, and `docs/PROJECT_CONTEXT.md` committed in baseline commit `67ab4ea`.
- **Known Blockers:** None.
- **Next Action:** Proceed to Milestone 02 — Source Validation Specification.

---

## Milestone 02 — Source Validation Specification
- **Goal:** Analyze the official HadeethEnc API contract and specify deterministic verification rules before writing any integration code.
- **Scope:** Document endpoints, response schemas, Arabic/English record correlation, reference validation, attribution policies, and rejection criteria.
- **Dependencies:** Milestone 01.
- **Acceptance Criteria:**
  - Detailed API contract in `docs/API_CONTRACTS.md`.
  - Deterministic reference matching rules defined.
  - Rejection policy established for incomplete or unverified records.
- **Current Status:** `Verified`
- **Verification Evidence:**
  - Empirical audit of live HadeethEnc REST endpoints (`/hadeeths/list/`, `/hadeeths/one/`, `/categories/list/`).
  - Discovered critical API contract detail: English payload omits `reference` key; Arabic payload contains canonical citation.
  - Specified two-step cross-verification invariant (`en.hadeeth_ar == ar.hadeeth`).
  - Defined deterministic regex parsing for Sahih al-Bukhari and Sahih Muslim reference numbers.
  - Comprehensive specification committed in `docs/API_CONTRACTS.md`.
- **Known Blockers:** None.
- **Next Action:** Proceed to Milestone 03 — Configuration and Secrets.

---

## Milestone 03 — Configuration and Secrets
- **Goal:** Build a robust, type-safe settings management layer with strict secret protection.
- **Scope:** Pydantic Settings implementation, `.env.example`, environment validation, and unit tests for configuration parsing.
- **Dependencies:** Milestone 02.
- **Acceptance Criteria:**
  - Settings load strictly from environment or `.env`.
  - Missing mandatory secrets fail fast with clear errors.
  - No secret values exposed in logs or defaults.
- **Current Status:** `Verified`
- **Verification Evidence:**
  - Python virtual environment `.venv` configured on Python 3.14.6 arm64.
  - Dependencies locked in `requirements.txt` and `pyproject.toml`.
  - `.env.example` created with comprehensive placeholder schema.
  - `src/config.py` implemented with Pydantic v2 BaseSettings, timezone validation, and safe secret masking.
  - Automated test suite `tests/test_config.py` passed 100% (6/6 tests passing).
- **Known Blockers:** None.
- **Next Action:** Proceed to Milestone 04 — Database Foundation.

---

## Milestone 04 — Database Foundation
- **Goal:** Set up persistence and migration-ready schemas connected directly to Neon PostgreSQL.
- **Scope:** ORM persistence layer, Alembic migration strategy, schemas for candidate status, execution history, and delivery idempotency.
- **Dependencies:** Milestone 03.
- **Acceptance Criteria:**
  - Database connected to Neon PostgreSQL over SSL pooler.
  - Schema migrations with Alembic run cleanly.
  - Candidate deduplication and idempotency queries verified.
  - 100% automated test pass rate for database operations.
- **Current Status:** `Verified`
- **Verification Evidence:**
  - Connected live to Neon PostgreSQL (PostgreSQL 18.6) over SSL pooler via `psycopg`.
  - Refactored persistence into modular `src/database/` package (`session.py`, `models.py`, `repository.py`).
  - Generated and stamped Alembic initial migration (`f02e818f721d_initial_schema.py`).
  - Database unique constraint on `DailyDeliveryLog.scheduled_date` enforces daily idempotency.
  - Repository layer implemented for candidate deduplication and delivery history.
  - 11/11 automated unit tests passing across `tests/test_database.py` and `tests/test_config.py`.
- **Known Blockers:** None.
- **Next Action:** Proceed to Milestone 05 — HadeethEnc Integration.

---

## Milestone 05 — HadeethEnc Integration
- **Goal:** Implement an HTTP client to fetch records from the official HadeethEnc API.
- **Scope:** English retrieval, Arabic counterpart pairing, error handling, rate limiting, and network timeout handling.
- **Dependencies:** Milestone 02, Milestone 03.
- **Acceptance Criteria:**
  - Client retrieves approved collection candidates without web scraping.
  - HTTP failure modes handled cleanly.
  - Raw payloads structured into typed internal representations.
- **Current Status:** `Verified`
- **Verification Evidence:**
  - Implemented typed Pydantic models in `src/hadeethenc/schemas.py` (`HadeethEncListResponse`, `HadeethEncEnglishDetail`, `HadeethEncArabicDetail`, `HadeethEncCandidatePair`).
  - Implemented resilient HTTP client in `src/hadeethenc/client.py` using `httpx` with timeout management, retry support, and typed custom domain exceptions (`HadeethEncNotFoundError`, `HadeethEncNetworkError`, etc.).
  - Implemented deterministic invariant verifier in `src/hadeethenc/verifier.py` enforcing `en.hadeeth_ar == ar.hadeeth`, approved attribution validation, and canonical reference regex extraction.
  - Comprehensive unit and contract tests in `tests/test_hadeethenc.py` with 14 mocked test scenarios. Full test suite passing 100% (25/25 tests passing in 0.27s).
  - Empirical live integration test executed against HadeethEnc production API validating end-to-end fetching, Arabic pairing, and reference parsing for real Hadiths (IDs: 5907, 5913).
- **Known Blockers:** None.
- **Next Action:** Proceed to Milestone 06 — Source Catalogue Audit.

---

## Milestone 06 — Source Catalogue Audit
- **Goal:** Audit candidate records across Sahih al-Bukhari and Sahih Muslim available via HadeethEnc.
- **Scope:** Check field completeness, translation versions, and reference consistency across candidate datasets.
- **Dependencies:** Milestone 05.
- **Acceptance Criteria:**
  - Representative records audited and documented.
  - Inconsistent or ambiguous records flagged for automatic rejection.
- **Current Status:** `Verified`
- **Verification Evidence:**
  - Empirical audit of HadeethEnc taxonomy (7 root categories, 452 subcategories, 2,776+ total Hadiths).
  - Executed empirical sampling across Tier-1 categories (Category 5: Virtues & Manners, Category 1: The Noble Qur’an).
  - Discovered structural distinction between precision citations (with volume/page/Hadith number) and bibliographic-only citations.
  - Hardened `verify_candidate_pair` in `src/hadeethenc/verifier.py` to reject records without an explicit Hadith number fail-closed (`ERR_AMBIGUOUS_CITATION`).
  - Added unit test `test_verifier_bibliographic_citation_without_number_fails` in `tests/test_hadeethenc.py` (26/26 tests passing).
  - Formalized comprehensive findings, candidate capacity analysis (~913 verified Hadiths / 2.5 years of daily delivery), and catalogue policy in `docs/SOURCE_CATALOGUE_AUDIT.md`.
- **Known Blockers:** None.
- **Next Action:** Proceed to Milestone 07 — Deterministic Validation Engine.

---

## Milestone 07 — Deterministic Validation Engine
- **Goal:** Build the strict deterministic gatekeeper domain pipeline ensuring only 100% verified Hadith can proceed.
- **Scope:** Typed domain validation models, candidate ingestion pipeline, database persistence integration, and fail-closed error handling.
- **Dependencies:** Milestone 04, Milestone 05, Milestone 06.
- **Acceptance Criteria:**
  - Malformed or unverified records rejected immediately with structured error codes.
  - Verified candidate pairs stored in Neon PostgreSQL candidate table.
  - 100% automated test coverage across domain validation rules.
- **Current Status:** `Verified`
- **Verification Evidence:**
  - Implemented domain candidate ingestion service in `src/ingestion/service.py` and exported facade in `src/ingestion/__init__.py`.
  - Connected dual HadeethEnc retrieval, invariant cross-verification, and Neon PostgreSQL database persistence.
  - Added 4 comprehensive unit and integration tests in `tests/test_ingestion.py` (verified persistence, rejection auditability, deduplication idempotency, and batch metrics).
  - All 30 automated tests passing 100% in 0.22s across config, database, hadeethenc, and ingestion test suites.
  - Executed live empirical batch ingestion against Neon PostgreSQL populating candidate queue (9 verified, 1 rejected).
  - Verified candidate queue retrieval via `get_next_verified_candidate()` returning Hadith ID 66511 (Agreed Upon #6953).
- **Known Blockers:** None.
- **Next Action:** Proceed to Milestone 08 — LangGraph Workflow.

---

## Milestone 08 — LangGraph Workflow
- **Goal:** Orchestrate the end-to-end processing pipeline using LangGraph state graphs.
- **Scope:** Define state schema, candidate fetching node, validation node, deduplication node, commentary generation node, and persistence node.
- **Dependencies:** Milestone 04, Milestone 07.
- **Acceptance Criteria:**
  - Conditional edges route failures to safe abort states.
  - State graph fully typed and unit tested with mock inputs.
- **Current Status:** `Verified`
- **Verification Evidence:**
  - Installed `langgraph>=0.2.0` (v1.2.20 verified on Python 3.14.6 arm64).
  - Implemented typed workflow state schema in `src/workflow/state.py` (`DailyWorkflowState`).
  - Implemented testable pure node functions in `src/workflow/nodes.py` (idempotency, candidate selection, defense-in-depth safety, message formatting, and delivery logging).
  - Built compiled StateGraph with conditional routing edges in `src/workflow/graph.py` and exported facade in `src/workflow/__init__.py`.
  - Added 4 automated unit tests in `tests/test_workflow.py` covering all 4 routing paths (happy path, idempotency skip, queue empty abort, safety abort). Full test suite achieves 34/34 passing in 0.27s.
  - Live empirical execution on Neon PostgreSQL completed delivery for Candidate 1 (Agreed Upon #6953) and demonstrated instant idempotency skip on subsequent execution.
- **Known Blockers:** None.
- **Next Action:** Proceed to Milestone 09 — Groq Integration.

---

## Milestone 09 — Groq Integration
- **Goal:** Integrate Groq LLM API to generate educational reflections/commentary.
- **Scope:** Groq API client, prompt design enforcing strict separation of commentary from original Hadith, and fallback behavior on LLM unavailability.
- **Dependencies:** Milestone 08.
- **Acceptance Criteria:**
  - Model never alters the original Hadith translation.
  - AI reflection clearly demarcated as non-source material.
  - LLM outages gracefully default to delivering verified Hadith alone (or fail closed based on policy).
- **Current Status:** `Verified`
- **Verification Evidence:**
  - Installed `groq>=0.9.0` (v1.7.0 verified on Python 3.14.6 arm64).
  - Implemented prompt template with strict negative theological constraints in `src/llm/prompts.py` (prohibiting fatwas, re-translation, or paraphrasing; capped at 120 words).
  - Built resilient `GroqReflectionClient` in `src/llm/client.py` with automatic graceful fallback when API keys are unconfigured, rate-limited, or services encounter network errors.
  - Exported facade in `src/llm/__init__.py` and documented architecture in `src/llm/README.md`.
  - Wired `generate_reflection` node into LangGraph StateGraph between safety verification and message formatting (`src/workflow/nodes.py` & `src/workflow/graph.py`).
  - Added 5 automated unit tests in `tests/test_llm.py`. Full test suite achieves 39/39 passing in 0.66s.
- **Known Blockers:** None.
- **Next Action:** Proceed to Milestone 10 — Guardrails AI.

---

## Milestone 10 — Guardrails AI
- **Goal:** Layer structural and content validation over LLM-generated reflection.
- **Scope:** Guardrails AI validators verifying commentary does not claim unverified theological rulings or fabricate citations.
- **Dependencies:** Milestone 09.
- **Acceptance Criteria:**
  - Guardrail failures trigger fallback or safe omission of commentary.
  - System performance and latency remain acceptable.
- **Current Status:** `Verified`
- **Verification Evidence:**
  - Implemented deterministic boundary rules in `src/guardrails/rules.py` (prohibiting fatwas, unauthorized citations, verbatim text leakage, and word count violations).
  - Implemented pure validation engine in `src/guardrails/validator.py` (`ReflectionValidator`, `validate_reflection`).
  - Integrated `validate_guardrails` node into LangGraph StateGraph between `generate_reflection` and `format_message`.
  - Added 10 automated unit tests in `tests/test_guardrails.py` and 2 workflow integration tests in `tests/test_workflow.py`.
  - Full automated test suite achieves 51/51 passing in 1.71s (100% pass rate).
- **Known Blockers:** None.
- **Next Action:** Proceed to Milestone 11 — Final Content Validation.

---

## Milestone 11 — Final Content Validation
- **Goal:** End-to-end verification of assembled notification payloads before delivery adapter implementation.
- **Scope:** Combined audit of Hadith source text, citation metadata, URL links, version tag, and AI reflection formatting.
- **Dependencies:** Milestone 08, Milestone 10.
- **Acceptance Criteria:**
  - Assembled messages verified against source integrity guidelines.
  - Zero hallucination or unverified reference leakage.
- **Current Status:** `Verified`
- **Verification Evidence:**
  - Implemented modular formatter package in `src/formatter/message.py` and exported facade in `src/formatter/__init__.py`.
  - Built `format_daily_hadith_message` enforcing Telegram HTML formatting, quote preservation (`quote=False`), and character limits (<= 4096 chars).
  - Enforced mandatory canonical metadata (Collection, citation reference, grade, source URL) and segregated non-canonical AI reflection disclaimer.
  - Added 4 contract tests in `tests/test_formatter.py` and updated workflow assertions. Full test suite achieves 55/55 passing in 1.52s.
- **Known Blockers:** None.
- **Next Action:** Proceed to Milestone 12 — Telegram Integration.

---

## Milestone 12 — Telegram Integration & Public Subscription Engine
- **Goal:** Enable anyone to publicly interact with the bot via a shareable link (`https://t.me/<bot_username>`), self-register or opt-out, query verified Hadiths on demand, and receive rate-limited daily notifications via the official Telegram Bot API.
- **Scope:**
  - **Outbound Telegram Adapter (`src/delivery/telegram.py`):** Typed `httpx.Client` adapter supporting message dispatch, webhook management (`setWebhook`, `getWebhookInfo`, `deleteWebhook`), and exponential backoff retry for network transients.
  - **Subscriber Database Model (`src/database/models.py` & Alembic):** `TelegramSubscriber` table (`id`, `chat_id` BigInteger Unique Index, `username`, `first_name`, `is_active`, `joined_at`, `updated_at`).
  - **Inbound Webhook Security (`src/delivery/router.py`):** FastAPI `POST /telegram/webhook` secured with constant-time verification of `X-Telegram-Bot-Api-Secret-Token`. Rejects missing, invalid, or forged tokens immediately with HTTP 403 Forbidden.
  - **Duplicate Registration Handling:** Idempotent registration logic in `src/database/repository.py` (`get_or_create_subscriber`). If a user sends `/start` repeatedly:
    - If already active: preserves existing record without creating duplicate rows or erroring.
    - If previously deactivated (`is_active = False` via `/stop` or temporary block): reactivates (`is_active = True`) seamlessly.
  - **Multi-User Isolation:** Each subscriber is keyed strictly by Telegram `chat_id`. Subscriber state, preferences, and delivery logs are isolated per user.
  - **Public Bot Commands:**
    - `/start`: Onboarding message, idempotent subscriber registration, and immediate dispatch of today's verified Hadith.
    - `/today` or `/hadith`: Instant fetch & dispatch of today's verified Hadith without altering subscription status.
    - `/stop` or `/unsubscribe`: Immediate opt-out (`is_active = False`) with clear confirmation message.
    - `/help`: Detailed reference explaining command usage, theological guardrails (immutable Hadith text), and canonical HadeethEnc attribution.
  - **Delivery Failure Recovery:**
    - If Telegram returns HTTP 403 Forbidden (`bot was blocked by the user`), automatically mark `TelegramSubscriber.is_active = False` to prevent future futile delivery attempts.
    - If Telegram returns HTTP 429 (`Too Many Requests`), honor `Retry-After` header with exponential backoff.
  - **Telegram Rate Limits:** Fan-out broadcaster throttles delivery to a maximum of 30 messages/second in compliance with Telegram API broadcast guidelines.
  - **Automated Test Suite (`tests/test_delivery.py`):** Unit and contract tests mocking Telegram Bot API endpoints (`sendMessage`, webhook updates, 403 bot-blocked, 429 rate limit, forged token rejection).
- **Dependencies:** Milestone 03, Milestone 11.
- **Acceptance Criteria:**
  - Inbound webhook processes `/start`, `/today`, `/stop`, and `/help` reliably.
  - Webhook rejects forged payloads lacking the valid secret token with HTTP 403.
  - Multiple users can register, query, and opt-out independently with full data isolation.
  - Repeated `/start` commands do not violate unique database constraints or duplicate subscriber records.
  - Bot blocking (HTTP 403) automatically deactivates the subscriber.
  - Outbound fan-out respects Telegram 30 msgs/sec rate limit.
- **Current Status:** `Verified`
- **Verification Evidence:**
  - Implemented `TelegramSubscriber` SQLAlchemy model (`chat_id` BigInteger unique index) and applied migration `547b6992865a_create_telegram_subscribers.py` to Neon PostgreSQL.
  - Implemented `TelegramClient` in `src/delivery/telegram.py` with retry backoff, HTTP 429 `Retry-After` parsing, HTTP 403 `TelegramBotBlockedError` handling, and webhook administration methods (`set_webhook`, `get_webhook_info`, `delete_webhook`).
  - Built FastAPI router in `src/delivery/router.py` verifying `X-Telegram-Bot-Api-Secret-Token` via `hmac.compare_digest` (HTTP 403 on invalid secret) and public commands (`/start`, `/today`, `/stop`, `/help`).
  - Wired `deliver_telegram_node` into LangGraph StateGraph between `format_message` and `record_delivery` with multi-user fan-out and automatic subscriber deactivation on HTTP 403.
  - Automated test suite achieves **68/68 passing tests** (100% pass rate) across all 9 test modules.
- **Known Blockers:** None.
- **Next Action:** Proceed to Milestone 13 — Scheduling & Daily Multi-User Broadcast.

---

## Milestone 13 — Scheduling & Daily Multi-User Broadcast
- **Goal:** Implement scheduled execution triggering daily notifications at 10:00 AM Asia/Kolkata fanning out to all active subscribers.
- **Scope:** Scheduler architecture (APScheduler / cron trigger / cloud trigger), timezone handling (`Asia/Kolkata`), multi-user fan-out coordination, Telegram 30 msg/sec rate-limit throttling, and misfire protection.
- **Dependencies:** Milestone 12.
- **Acceptance Criteria:**
  - Job correctly fires daily according to `Asia/Kolkata` wall-clock time (10:00 AM).
  - Delivers to 100% of active opted-in subscribers without exceeding Telegram rate limits.
  - Misfire grace times and restart scenarios tested and documented.
- **Current Status:** `Verified`
- **Verification Evidence:**
  - Implemented headless CLI runner in `src/workflow/daily_runner.py` supporting `--date`, `--dry-run`, structured logging, and system exit codes.
  - Implemented in-process background scheduler in `src/workflow/scheduler.py` configured for `Asia/Kolkata` at 10:00 AM IST with 3600-second (1-hour) misfire recovery and coalesce protection.
  - Built unified FastAPI server in `src/main.py` mounting container `/health` check, `/telegram/webhook` router, authenticated `POST /api/cron/daily-broadcast` for Cloud Scheduler, and lifespan scheduler management.
  - Added automated test suite in `tests/test_scheduler.py` covering runner dry-run execution, timezone/misfire configuration, container health checks, and cron endpoint authentication.
  - Full automated test suite achieves **72/72 passing tests** (100% pass rate).
- **Known Blockers:** None.
- **Next Action:** Proceed to Milestone 14 — History & Per-Subscriber Daily Idempotency.

---

## Milestone 14 — History & Per-Subscriber Daily Idempotency
- **Goal:** Prevent duplicate daily sends per subscriber under retries, restarts, or scheduler hiccups.
- **Scope:** Database composite unique constraint `(subscriber_id, scheduled_date)` or `(chat_id, scheduled_date)`, execution lock records, and per-user delivery attempt auditing.
- **Dependencies:** Milestone 04, Milestone 13.
- **Acceptance Criteria:**
  - Re-running the scheduler within the same calendar day safely skips already-delivered subscribers.
  - Each subscriber receives exactly one notification per calendar day.
  - Delivery outcome, latency, and message ID recorded for every subscriber dispatch.
- **Current Status:** `Verified`
- **Verification Evidence:**
  - Created `SubscriberDeliveryLog` SQLAlchemy model in `src/database/models.py` with composite unique constraint `uq_subscriber_daily_delivery` on `(subscriber_id, scheduled_date)`.
  - Added repository methods in `src/database/repository.py`: `record_subscriber_delivery()`, `get_undelivered_active_subscribers()`, and `is_subscriber_delivered()`.
  - Autogenerated and applied Alembic migration `59d6a20998f2_create_subscriber_delivery_logs.py` directly to Neon PostgreSQL.
  - Updated `deliver_telegram_node` in `src/workflow/nodes.py` to query only undelivered active subscribers, record `DELIVERED`, `BLOCKED`, or `FAILED` per subscriber, and commit per message for mid-run crash recovery.
  - Created `tests/test_idempotency.py` verifying composite unique constraint violation handling, mid-run crash recovery skipping delivered users, and zero messages sent on complete rerun.
  - Automated test suite achieved **75/75 passing tests** (100% pass rate in 8.89s).
- **Known Blockers:** None.
- **Next Action:** Proceed to Milestone 15 — Failure Handling.

---

## Milestone 15 — Failure Handling
- **Goal:** Stress-test system resilience across all external dependencies.
- **Scope:** Test scenarios: HadeethEnc API down, Groq rate limited, Telegram timeout, database connection loss, invalid source data.
- **Dependencies:** Milestones 04 through 14.
- **Acceptance Criteria:**
  - System fails closed without corrupting database state or sending garbled messages.
  - Operational errors logged with actionable diagnostic context.
- **Current Status:** `Verified`
- **Verification Evidence:**
  - Created dedicated failure handling test suite in `tests/test_failure_handling.py` (19 comprehensive unit and integration stress tests).
  - Verified upstream HadeethEnc API outage fail-closed invariants (HTTP 500/503 raises `HadeethEncResponseError`, network timeouts raise `HadeethEncNetworkError`, malformed HTML raises `HadeethEncResponseError`, and category batch ingestion survives partial failures without aborting valid candidates).
  - Verified Groq LLM degradation resilience (missing key returns `OMITTED`, rate limits or API exceptions return `FAILED`, and theological fatwa/decree violations are cleanly omitted while delivering authentic Hadith text).
  - Verified Telegram Bot API resilience (HTTP 500 transient backoff retries and succeeds, HTTP 500 exhaustion raises `TelegramDeliveryError`, >4096 character overflow fails closed, and mixed fan-out delivery cleanly isolates delivered, blocked, and failed subscribers).
  - Verified inbound webhook resilience (constant-time forged secret 403, missing secret 403, unparseable JSON non-crash response, non-message update ignored, unrecognized slash command guidance).
  - Verified database integrity and idempotency constraints (daily delivery log unique date constraint and subscriber delivery log composite unique constraint).
  - Full automated test suite achieves **94/94 passing tests (100% pass rate in 16.75s)** across all 12 modules.
- **Known Blockers:** None.
- **Next Action:** Proceed to Milestone 16 — Automated Testing & Code Quality.

---

## Milestone 16 — Automated Testing & Code Quality
- **Goal:** Implement comprehensive test suite with automated linting and formatting.
- **Scope:** Unit tests, integration tests with mocks, Ruff linting/formatting checks, and test coverage reporting.
- **Dependencies:** Milestone 15.
- **Acceptance Criteria:**
  - `pytest` passes 100% of tests.
  - `ruff check` and `ruff format` pass without warnings.
- **Current Status:** `Verified`
- **Verification Evidence:**
  - Configured repository-wide Ruff standards in `pyproject.toml` (`line-length = 100`, isort, flake8-bugbear, pyupgrade).
  - Executed `ruff check .` across all 65 Python files with zero warnings or lint errors.
  - Executed `ruff format .` formatting 100% of codebase to PEP 8 standards.
  - Executed `pytest --cov=src --cov-report=term-missing` achieving **94/94 passing tests (100% pass rate in 17.13s)** with **89% total test coverage** across `src/` (core packages `src.database`, `src.formatter`, `src.guardrails`, `src.workflow` reaching 94–100% coverage).
- **Known Blockers:** None.
- **Next Action:** Proceed to Milestone 17 — Docker Containerization.

---

## Milestone 17 — Docker Containerization
- **Goal:** Package the application into an immutable, secure Docker container.
- **Scope:** Multi-stage `Dockerfile`, non-root user execution, lightweight base image, `.dockerignore`, container health check.
- **Dependencies:** Milestone 16.
- **Acceptance Criteria:**
  - Container builds reproducibly without embedded secrets.
  - Container runs non-root and responds cleanly to `/health`.
- **Current Status:** `Verified`
- **Verification Evidence:**
  - Implemented multi-stage `Dockerfile` (`python:3.13-slim` builder compiling wheels, unprivileged `runtime` container ~160MB).
  - Hardened container security: non-root execution (`appuser:appgroup`, UID 10001), `PYTHONUNBUFFERED=1`, `PYTHONDONTWRITEBYTECODE=1`, zero embedded credentials.
  - Implemented comprehensive `.dockerignore` excluding `.env*`, `.venv/`, `.git/`, `tests/`, and cache artifacts.
  - Configured container `HEALTHCHECK` probing `GET /health` on port 8080.
  - Created `docker-compose.yml` for local container orchestration.
  - Created automated test suite in `tests/test_container.py` (5 tests covering multi-stage structure, non-root user, ignore patterns, Compose config, and `/health` probe response).
  - Full automated test suite achieves **99/99 passing tests (100% pass rate in 16.32s)** with **89% code coverage**.
- **Known Blockers:** None.
- **Next Action:** Proceed to Milestone 18 — Cloud Deployment.

---

## Milestone 18 — Cloud Deployment
- **Goal:** Deploy the containerized FastAPI service and scheduler to cloud hosting backed by Neon PostgreSQL.
- **Scope:** Production environment configuration, database migration on deploy, Cloud Scheduler trigger verification, secure secret management.
- **Dependencies:** Milestone 17.
- **Acceptance Criteria:**
  - Application deployed and connected to Neon PostgreSQL.
  - Scheduled run triggers successfully in production environment.
- **Current Status:** `Verified`
- **Verification Evidence:**
  - Deployed containerized FastAPI service to Render Free Web Service (`https://daily-hadith-ai-agent.onrender.com`).
  - Verified live container healthcheck (`GET /health`) returning HTTP 200 with `status: "healthy"`, `environment: "production"`, and `timezone: "Asia/Kolkata"`.
  - Configured and verified live Telegram inbound webhook pointing to `https://daily-hadith-ai-agent.onrender.com/telegram/webhook` secured with constant-time secret token header validation (`X-Telegram-Bot-Api-Secret-Token`).
  - Verified end-to-end user interaction on Telegram: user `/start` received, subscriber record `GOKU` (Chat ID `746451674`) successfully registered and persisted in Neon PostgreSQL database (`telegram_subscribers` table), and onboarding Hadith from Sahih Muslim (#1955) delivered instantly.
  - Configured automated 10:00 AM IST daily broadcast cron trigger on cron-job.org executing `POST /api/cron/daily-broadcast` with authenticated `X-Cron-Secret` header.
- **Known Blockers:** None.
- **Next Action:** Proceed to Milestone 19 — Production Readiness.

---

## Milestone 19 — Production Readiness
- **Goal:** Final system audit against all non-functional requirements and portfolio presentation.
- **Scope:** Full runbook verification, architecture documentation review, license and attribution compliance, security posture check.
- **Dependencies:** Milestone 18.
- **Acceptance Criteria:**
  - All 20 Definition of Done criteria verified with concrete proof.
  - Runbook verified through dry-run operation.
- **Current Status:** `Not Started`
- **Verification Evidence:** None.
- **Known Blockers:** None.
- **Next Action:** Await Milestone 18.

---

## Milestone 20 — Future FCM Support (Evaluation)
- **Goal:** Architectural evaluation and technical spike for Firebase Cloud Messaging mobile push notifications.
- **Scope:** Feasibility analysis, payload schemas, and migration path from Telegram-only to multi-channel notifications.
- **Dependencies:** Milestone 19.
- **Acceptance Criteria:**
  - Technical design document outlining FCM integration strategy.
- **Current Status:** `Not Started`
- **Verification Evidence:** None.
- **Known Blockers:** Deferred to post-V1.
- **Next Action:** Await Milestone 19.