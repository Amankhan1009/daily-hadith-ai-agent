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
| 05 | HadeethEnc Integration | Not Started |
| 06 | Source Catalogue Audit | Not Started |
| 07 | Deterministic Validation | Not Started |
| 08 | LangGraph Workflow | Not Started |
| 09 | Groq Integration | Not Started |
| 10 | Guardrails AI | Not Started |
| 11 | Final Content Validation | Not Started |
| 12 | Telegram Integration | Not Started |
| 13 | Scheduling | Not Started |
| 14 | History and Idempotency | Not Started |
| 15 | Failure Handling | Not Started |
| 16 | Automated Testing | Not Started |
| 17 | Docker Containerization | Not Started |
| 18 | Cloud Deployment | Not Started |
| 19 | Production Readiness | Not Started |
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
- **Current Status:** `In Progress`
- **Verification Evidence:** None.
- **Known Blockers:** None.
- **Next Action:** Audit Guardrails AI dependencies on Python 3.14 and define hallucination prevention rails in `src/guardrails/`.

---

## Milestone 11 — Final Content Validation
- **Goal:** End-to-end verification of assembled notification payloads before delivery adapter implementation.
- **Scope:** Combined audit of Hadith source text, citation metadata, URL links, version tag, and AI reflection formatting.
- **Dependencies:** Milestone 08, Milestone 10.
- **Acceptance Criteria:**
  - Assembled messages verified against source integrity guidelines.
  - Zero hallucination or unverified reference leakage.
- **Current Status:** `Not Started`
- **Verification Evidence:** None.
- **Known Blockers:** None.
- **Next Action:** Await Milestone 10.

---

## Milestone 12 — Telegram Integration
- **Goal:** Deliver formatted daily notifications via official Telegram Bot API.
- **Scope:** Telegram bot adapter, HTML/Markdown formatting, message length safeguards, rate limit handling, and secure credential handling.
- **Dependencies:** Milestone 03, Milestone 11.
- **Acceptance Criteria:**
  - Manually triggered test message delivers cleanly to Telegram chat.
  - Source links, attribution, and AI disclaimer render legibly.
  - Network and API failures handled with retry/backoff.
- **Current Status:** `Not Started`
- **Verification Evidence:** None.
- **Known Blockers:** None.
- **Next Action:** Await Milestone 11.

---

## Milestone 13 — Scheduling
- **Goal:** Implement scheduled execution triggering daily notifications at 10:00 AM Asia/Kolkata.
- **Scope:** Scheduler architecture (APScheduler / cron trigger / cloud trigger), timezone handling, misfire protection, and restart recovery.
- **Dependencies:** Milestone 12.
- **Acceptance Criteria:**
  - Job correctly fires according to `Asia/Kolkata` wall-clock time.
  - Misfire grace times and restart scenarios tested and documented.
- **Current Status:** `Not Started`
- **Verification Evidence:** None.
- **Known Blockers:** None.
- **Next Action:** Await Milestone 12.

---

## Milestone 14 — History and Idempotency
- **Goal:** Prevent duplicate daily sends under retries, restarts, or scheduler hiccups.
- **Scope:** Database unique constraints, execution lock records, and delivery attempt logging.
- **Dependencies:** Milestone 04, Milestone 13.
- **Acceptance Criteria:**
  - Re-running the scheduler within the same calendar day safely skips delivery.
  - Delivery outcome and latency recorded for every trigger.
- **Current Status:** `Not Started`
- **Verification Evidence:** None.
- **Known Blockers:** None.
- **Next Action:** Await Milestone 13.

---

## Milestone 15 — Failure Handling
- **Goal:** Stress-test system resilience across all external dependencies.
- **Scope:** Test scenarios: HadeethEnc API down, Groq rate limited, Telegram timeout, database connection loss, invalid source data.
- **Dependencies:** Milestones 04 through 14.
- **Acceptance Criteria:**
  - System fails closed without corrupting database state or sending garbled messages.
  - Operational errors logged with actionable diagnostic context.
- **Current Status:** `Not Started`
- **Verification Evidence:** None.
- **Known Blockers:** None.
- **Next Action:** Await Milestone 14.

---

## Milestone 16 — Automated Testing
- **Goal:** Implement comprehensive test suite with automated linting and formatting.
- **Scope:** Unit tests, integration tests with mocks, Ruff linting/formatting checks, and test coverage reporting.
- **Dependencies:** Milestone 15.
- **Acceptance Criteria:**
  - `pytest` passes 100% of tests.
  - `ruff check` and `ruff format` pass without warnings.
- **Current Status:** `Not Started`
- **Verification Evidence:** None.
- **Known Blockers:** None.
- **Next Action:** Await Milestone 15.

---

## Milestone 17 — Docker Containerization
- **Goal:** Package the application into an immutable, secure Docker container.
- **Scope:** Multi-stage `Dockerfile`, non-root user execution, lightweight base image, `.dockerignore`, container health check.
- **Dependencies:** Milestone 16.
- **Acceptance Criteria:**
  - Container builds reproducibly without embedded secrets.
  - Container runs and passes internal health checks.
- **Current Status:** `Not Started`
- **Verification Evidence:** None.
- **Known Blockers:** None.
- **Next Action:** Await Milestone 16.

---

## Milestone 18 — Cloud Deployment
- **Goal:** Deploy the FastAPI service and scheduler to cloud hosting (e.g., Render) backed by Neon PostgreSQL.
- **Scope:** Production environment configuration, database migration on deploy, scheduler verification, secure secret management.
- **Dependencies:** Milestone 17.
- **Acceptance Criteria:**
  - Application deployed and connected to Neon PostgreSQL.
  - Scheduled run triggers successfully in production environment.
- **Current Status:** `Not Started`
- **Verification Evidence:** None.
- **Known Blockers:** None.
- **Next Action:** Await Milestone 17.

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