# Project Context & Developer Handover

> **Durable Source of Truth for Development Continuity**  
> *Last Updated:* Milestone 11 Verified

---

## 1. What We Are Building
An AI-assisted, production-grade notification application and public Telegram bot named **Daily Hadith AI Agent**. It delivers verified English Hadith notifications to registered subscribers on Telegram every day at **10:00 AM Asia/Kolkata**.

Anyone can access the bot publicly via its shareable link (`https://t.me/<bot_username>`) to:
1. **Subscribe via `/start`**: Receive a warm onboarding welcome, instant registration, and immediate delivery of today's verified Hadith.
2. **On-Demand Query via `/today`**: Request today's verified Hadith at any time.
3. **Opt-Out via `/stop`**: Unsubscribe immediately with instant confirmation.
4. **Learn via `/help`**: Inspect theological boundaries, source provenance, translation attribution, and system guarantees.

Each daily broadcast notification contains:
1. Exact, unchanged English Hadith text retrieved from an approved source ([HadeethEnc](https://hadeethenc.com/en/home)).
2. Verified collection name and citation reference.
3. Canonical source-page URL.
4. Source attribution and translation version metadata.
5. An optional, clearly segregated and labeled AI reflection (strictly non-canonical commentary).

---

## 2. Why We Are Building It
This is a portfolio-grade demonstration of dependable, fail-closed AI engineering:
- Orchestrating a deterministic validation pipeline alongside an LLM using **LangGraph**.
- Strict separation between canonical immutable source data and generative AI commentary.
- Production-grade backend architecture, automated testing, idempotent scheduling, containerization, and cloud deployment.
- Demonstrating that in high-stakes domains (theological, legal, medical), AI must be bounded by deterministic verification gates.

---

## 3. High-Level Architecture & Flow

```mermaid
flowchart TD
    subgraph Ingestion & Verification [1. Ingestion & Deterministic Verification]
        A[HadeethEnc API] --> B[Candidate Retrieval EN + AR]
        B --> C[English & Arabic Metadata Matching]
        C --> D[Reference & Provenance Regex Grammar]
        D --> E{Passes Deterministic Gate?}
        E -- No --> F[Safe Abort & Audit Log]
        E -- Yes --> G[Neon PostgreSQL Candidate Queue]
    end

    subgraph User Interaction [2. Public Multi-User Webhook Engine]
        TG_User[Public Telegram Users] -->|"/start, /today, /stop, /help"| WH[FastAPI Webhook: POST /telegram/webhook]
        WH -->|Verify X-Telegram-Bot-Api-Secret-Token| SecGate{Valid Secret?}
        SecGate -- Invalid --> SecReject[Reject 403 Forbidden]
        SecGate -- Valid --> CmdRouter[Telegram Command Router]
        CmdRouter -->|/start (Idempotent)| SubRepo[(Neon DB: TelegramSubscriber)]
        CmdRouter -->|/stop| DeactSub[Deactivate Subscriber]
        CmdRouter -->|/today or Onboarding| InstantSend[Dispatch Today's Hadith]
    end

    subgraph Daily Pipeline [3. LangGraph Orchestration & Daily Broadcast]
        Scheduler[Daily Scheduler: 10:00 AM IST] --> LG[LangGraph Daily StateGraph]
        LG --> IdempCheck{Idempotency Check}
        IdempCheck -- Already Ran --> SkipDaily[Skip Run]
        IdempCheck -- New Day --> SelectCandidate[Select Candidate Queue Item]
        SelectCandidate --> GroqLLM[Groq LLM Reflection: gpt-oss-120b]
        GroqLLM --> GuardGate{Guardrails AI Gate}
        GuardGate -- Violation --> OmitReflection[Omit Reflection: Fail-Safe]
        GuardGate -- Valid --> FormatMsg[Format Canonical HTML Payload]
        OmitReflection --> FormatMsg
        FormatMsg --> FanOut[Multi-User Fan-Out Broadcaster]
        SubRepo -->|Active Subscribers| FanOut
        FanOut -->|30 msg/sec Rate Limit Throttling| TG_Dispatch[Telegram Bot API: sendMessage]
        TG_Dispatch -->|HTTP 403 Blocked| AutoDeact[Auto-Deactivate Blocked User]
        TG_Dispatch -->|Success / Retry| RecordDelivery[Record Per-Subscriber Delivery Log]
    end
```

---

## 4. Selected Technology Stack
- **Language:** Python 3.14.6 (macOS arm64 environment; package compatibility with dependencies to be audited in Milestone 03).
- **AI Orchestration:** LangGraph (typed state graph with conditional edges).
- **LLM Provider:** Groq (`openai/gpt-oss-120b` or verified equivalent available model).
- **Validation:** Pydantic v2, deterministic Python verification, Guardrails AI.
- **Backend Framework:** FastAPI.
- **Database:** SQLite (local development), Neon PostgreSQL (production deployment).
- **Notification Provider:** Telegram Bot API.
- **Search & Secondary Research (MCP):** Tavily via MCP (strictly for auxiliary verification, never as primary Hadith source).
- **Quality & DevOps:** pytest, Ruff, Docker, Git/GitHub.
- **Target Deployment:** Render / containerized worker + Neon PostgreSQL.

---

## 5. Approved Source Strategy
- **Primary Source:** HadeethEnc (official public API: `https://hadeethenc.com/en/home`).
- **Target Collections:** Sahih al-Bukhari and Sahih Muslim.
- **Coverage Policy:** HadeethEnc is recognized as a curated selection, not an exhaustive repository.
- **English Translation:** Mandatory. LLM is strictly prohibited from generating or modifying Hadith text.
- **Verification Rule:** Every English record must be paired with its Arabic counterpart to verify reference integrity and canonical provenance.
- **Fail-Closed Principle:** Any record with missing metadata, mismatched references, or ambiguous provenance is rejected immediately.
- **No Scraping:** Only official API endpoints or permitted official exports are used.

---

## 6. Current Milestone and Task
- **Active Milestone:** Milestone 14 — History & Per-Subscriber Daily Idempotency
- **Active Task:** Task 14.1 — Per-Subscriber Idempotency Schema and Composite Unique Constraints

---

## 7. Completed and Verified Work
- [x] **Milestone 13 Verified:** Scheduling & Daily Multi-User Broadcast.
  - Implemented headless CLI runner in `src/workflow/daily_runner.py` supporting `--date`, `--dry-run`, structured logging, and system exit codes.
  - Implemented in-process background scheduler in `src/workflow/scheduler.py` configured for `Asia/Kolkata` at 10:00 AM IST with 3600-second (1-hour) misfire recovery and coalesce protection.
  - Built unified FastAPI server in `src/main.py` mounting container `/health` check, `/telegram/webhook` router, authenticated `POST /api/cron/daily-broadcast` for Cloud Scheduler, and lifespan scheduler management.
  - Added automated test suite in `tests/test_scheduler.py` covering runner dry-run execution, timezone/misfire configuration, container health checks, and cron endpoint authentication.
  - Full automated test suite achieves **72/72 passing tests** (100% pass rate).
- [x] **Milestone 12 Verified:** Telegram Integration & Public Subscription Engine.
  - Implemented `TelegramSubscriber` SQLAlchemy model (`chat_id` BigInteger unique index) and applied migration `547b6992865a_create_telegram_subscribers.py` to Neon PostgreSQL.
  - Implemented `TelegramClient` in `src/delivery/telegram.py` with exponential backoff, rate limiting (25 msg/sec), HTTP 429 `Retry-After` parsing, HTTP 403 `TelegramBotBlockedError` handling, and webhook administration methods.
  - Built FastAPI router in `src/delivery/router.py` with timing-safe `X-Telegram-Bot-Api-Secret-Token` verification (HTTP 403 on invalid token) and public commands (`/start`, `/today`, `/stop`, `/help`).
  - Wired `deliver_telegram_node` into LangGraph StateGraph between `format_message` and `record_delivery` supporting multi-user fan-out and automatic subscriber deactivation on HTTP 403.
  - Automated test suite achieves **68/68 passing tests** (100% pass rate) across all 9 test modules.
- [x] **Milestone 01 Verified:** Project foundation, Git setup, directories, roadmap, context, and README committed (`67ab4ea`, `8162470`).
- [x] **Milestone 02 Verified:** Source Validation Specification (`58b7256`).
  - Live empirical audit of HadeethEnc endpoints.
  - Invariant defined: `en.hadeeth_ar == ar.hadeeth`.
  - Deterministic regex grammar specified for Bukhari and Muslim citations.
  - Rejection matrix and test cases formalized in `docs/API_CONTRACTS.md`.
- [x] **Milestone 03 Verified:** Configuration and Secrets (`e848cf0`).
  - Virtual environment `.venv` configured on Python 3.14.6 arm64.
  - `requirements.txt` and `pyproject.toml` established.
  - `.env.example` created with strict zero-secret placeholders.
  - `src/config.py` implemented with Pydantic v2 `BaseSettings` and safe secret masking.
  - `tests/test_config.py` automated unit test suite passing 6/6 tests.
- [x] **Milestone 11 Verified:** Final Content Validation & Formatter Architecture.
  - Implemented modular `src/formatter/message.py` and `src/formatter/__init__.py` assembling Telegram-compliant HTML payloads.
  - Enforced selective entity escaping (`quote=False`) to avoid mangling Arabic transliterated quotes (e.g. `Qur'an`), while strictly neutralizing HTML injection (`<`, `>`, `&`).
  - Guaranteed Telegram 4096-character limit enforcement fail-closed.
  - Added 4 contract tests in `tests/test_formatter.py` and integrated formatter directly into LangGraph `format_message_node`.
  - Full automated test suite achieves 55/55 passing in 1.52s.
- [x] **Milestone 10 Verified:** Guardrails AI & Reflection Safety Verification.
  - Implemented deterministic boundary rules in `src/guardrails/rules.py` (prohibiting fatwas, unauthorized citations, verbatim text leakage, and word count violations).
  - Implemented pure validation engine in `src/guardrails/validator.py` (`ReflectionValidator`, `validate_reflection`).
  - Integrated `validate_guardrails` node into LangGraph StateGraph in `src/workflow/graph.py` and `src/workflow/nodes.py`.
  - Added 10 automated unit tests in `tests/test_guardrails.py` and 2 workflow integration tests in `tests/test_workflow.py`.
  - Full automated test suite achieves 51/51 passing in 1.71s (100% pass rate).
- [x] **Milestone 09 Verified:** Groq Integration & Reflection Fallback.
  - Installed `groq>=0.9.0` (version 1.7.0 verified on Python 3.14.6 arm64).
  - Created `src/llm/prompts.py` enforcing strict theological negative constraints (no text modification, no fatwas, practical reflections capped under 120 words).
  - Created `src/llm/client.py` (`GroqReflectionClient`) with resilient failover to `OMITTED` (when `GROQ_API_KEY` is not provided) or `FAILED` (upon API error) without halting Hadith delivery.
  - Exported facade in `src/llm/__init__.py` and documented package in `src/llm/README.md`.
  - Integrated `generate_reflection` node into LangGraph StateGraph in `src/workflow/graph.py` and `src/workflow/nodes.py`.
  - Added 5 unit tests in `tests/test_llm.py`. Full test suite achieves 39/39 passing in 1.68s.
- [x] **Milestone 08 Verified:** LangGraph StateGraph Workflow & Live Idempotency.
  - Installed `langgraph>=0.2.0` (version 1.2.20 verified on Python 3.14.6).
  - Implemented typed state schema in `src/workflow/state.py` (`DailyWorkflowState`).
  - Implemented pure node functions in `src/workflow/nodes.py` (idempotency check, queue selection, defense-in-depth safety validation, Telegram formatting, and delivery logging).
  - Built compiled StateGraph with conditional edge routers in `src/workflow/graph.py` and exported facade in `src/workflow/__init__.py`.
  - Built 4 automated unit tests in `tests/test_workflow.py` validating all 4 branching pathways (happy path, idempotency skip, queue empty abort, safety abort).
  - Full test suite achieves 34/34 passing in 0.27s.
  - Live empirical execution on Neon PostgreSQL completed delivery for Candidate 1 (Agreed Upon #6953) and demonstrated instant idempotency skip on subsequent execution.
- [x] **Milestone 07 Verified:** Deterministic Validation Engine & Candidate Ingestion.
  - Implemented `CandidateIngestionService` and `ingest_candidate_pair` in `src/ingestion/service.py`.
  - Integrated dual HadeethEnc retrieval, deterministic verification, deduplication, and database persistence.
  - Built 4 automated unit and integration tests in `tests/test_ingestion.py` covering verified persistence, rejection auditability, deduplication, and batch metrics.
  - Full test suite achieves 30/30 passing in 0.22s.
  - Empirical live ingestion executed against Neon PostgreSQL inserting 9 verified and 1 rejected candidates from Category 5.
  - Proved candidate queue readiness via `get_next_verified_candidate()` (Candidate ID 66511: Agreed Upon #6953).
- [x] **Milestone 06 Verified:** Source Catalogue Audit & Acceptance Policy.
  - Audited HadeethEnc root taxonomy (7 root categories, 452 subcategories, 2,776+ Hadiths).
  - Sampled Tier-1 categories (Virtues & Manners, Noble Qur’an) demonstrating 60–75% empirical pass rates.
  - Discovered and addressed bibliographic-only citations; hardened verifier to reject records lacking explicit Hadith numbers fail-closed.
  - Established sustainable candidate pool sizing (~913 verified Hadiths, supporting 2.5 years of non-repeating delivery).
  - Formalized audit findings and acceptance rules in `docs/SOURCE_CATALOGUE_AUDIT.md`.
- [x] **Milestone 05 Verified:** HadeethEnc Integration & Deterministic Verifier.
  - Implemented typed Pydantic v2 schemas (`src/hadeethenc/schemas.py`) for list responses, English/Arabic detail payloads, and paired candidate structures.
  - Created robust `HadeethEncClient` (`src/hadeethenc/client.py`) with timeout controls, retries, and typed domain exceptions (`HadeethEncNotFoundError`, `HadeethEncNetworkError`, `HadeethEncResponseError`).
  - Implemented deterministic cross-verifier (`src/hadeethenc/verifier.py`) enforcing cross-payload Arabic text identity (`en.hadeeth_ar == ar.hadeeth`), collection attribution validation, and regex canonical citation extraction.
  - Added 14 comprehensive unit and contract tests in `tests/test_hadeethenc.py` using `httpx.MockTransport`. Full test suite achieves 25/25 passing in 0.27s.
  - Verified live against HadeethEnc production API with real Hadith records (`5907`, `5913`).
- [x] **Milestone 04 Verified:** Database Foundation & Neon PostgreSQL.
  - Connected directly to Neon PostgreSQL (PostgreSQL 18.6) over SSL pooler using modern `psycopg` driver.
  - Refactored persistence into modular `src/database/` package (`session.py`, `models.py`, `repository.py`).
  - Generated and stamped Alembic initial migration (`f02e818f721d_initial_schema.py`).
  - Database unique constraint on `DailyDeliveryLog.scheduled_date` enforces daily idempotency.
  - Repository layer implemented for candidate deduplication and delivery history.
  - 11/11 automated unit tests passing across `tests/test_database.py` and `tests/test_config.py`.

---

## 8. Work in Progress
- **Milestone 14: History & Per-Subscriber Daily Idempotency**
  - **Task 14.1:** Per-Subscriber Delivery Log Table (`subscriber_delivery_logs`) with `UNIQUE (subscriber_id, scheduled_date)` constraint.
  - **Task 14.2:** Resilient Mid-Run Recovery Query (skipping already-delivered users on retries).
  - **Task 14.3:** Alembic Migration & Idempotency Invariant Verification.

---

## 9. Open Questions and Technical Blockers
1. **Local Webhook Testing:** Telegram webhooks require a publicly accessible HTTPS URL. During local development, developers can either:
   - Use reverse tunneling tools (e.g., ngrok or cloudflared) pointing to local port 8000, OR
   - Run our automated test suite which tests signed webhook payloads directly via FastAPI TestClient.

---

## 10. Key Architecture Decisions (ADR Summary)
- **ADR-001 (Developer Control):** The developer maintains absolute manual control over all code, configuration, and Git operations. The AI assistant acts strictly as mentor/reviewer and never edits workspace files directly.
- **ADR-002 (Fail-Closed Content Safety):** The system must fail closed. Under no circumstances may an LLM hallucinate, translate, or paraphrase sacred text. If validation fails, zero message is sent.
- **ADR-003 (Deterministic Gatekeeping):** Theological validation is strictly deterministic (Pydantic + exact metadata matching). Generative AI is restricted to supplementary reflections only.
- **ADR-004 (Telegram for V1 Delivery):** Telegram Bot API is the single confirmed notification channel for V1, utilizing secure bot tokens and explicit chat IDs.
- **ADR-005 (Public Multi-User Subscription, Webhook Security & Rate Limiting):**
  - Public access is enabled via an inbound Telegram webhook endpoint (`POST /telegram/webhook`) secured with `X-Telegram-Bot-Api-Secret-Token`.
  - Subscribers are tracked in a dedicated `telegram_subscribers` table with idempotent `/start` registration (reactivates if inactive, ignores duplicates).
  - Outbound daily broadcast iterates active subscribers with rate limit throttling (30 messages/second compliance) to prevent Telegram API 429 penalties.
  - Delivery failures due to user blocking (HTTP 403 Forbidden) automatically update the subscriber record to `is_active = False` to prevent repeated futile dispatches.

---

## 11. Important Constraints
- **Zero Hardcoded Secrets:** No API keys, bot tokens, webhook secrets, or database URLs in source code or commits.
- **Attribution Integrity:** Every delivered message must retain publisher attribution, translation version, and canonical link.
- **Idempotent Delivery:** The scheduler and persistence layer must ensure at most one delivery per calendar day per subscriber.
- **Telegram Rate Limits:** Broadcasts must strictly respect Telegram's limit of 30 messages/second to avoid HTTP 429 penalties.
- **Multi-User Isolation:** Each subscriber's interactions, opt-ins, and daily delivery records must be isolated.

---

## 12. Exact Next Action
Begin Milestone 14: Per-Subscriber Delivery Logging & Composite Unique Idempotency Schema.

---

## 13. Latest Verification Evidence
- **72/72 Automated Tests Passing:** 100% pass rate in 6.3s across all 10 modules (`tests/test_config.py`, `tests/test_database.py`, `tests/test_delivery.py`, `tests/test_formatter.py`, `tests/test_guardrails.py`, `tests/test_hadeethenc.py`, `tests/test_ingestion.py`, `tests/test_llm.py`, `tests/test_scheduler.py`, `tests/test_workflow.py`).
- **Headless Runner CLI Verified:** `python -m src.workflow.daily_runner` supports `--dry-run`, custom dates, structured execution logging, and exit codes.
- **Timezone & Misfire Protection Verified:** `APScheduler` configured for `Asia/Kolkata` at 10:00 AM IST with 1-hour misfire grace time and coalesce protection.
- **FastAPI Unified Endpoints Verified:** Container `/health` status check and authenticated `POST /api/cron/daily-broadcast` for Cloud Scheduler.

---

## 14. Known Limitations
- Current scope is restricted to curated Hadith available on HadeethEnc; complete exhaustive collections are out of scope for V1.
- Inbound webhooks require a publicly accessible HTTPS endpoint (or reverse tunnel during local development) to receive Telegram updates in real time.
- Single notification channel (Telegram) for V1; mobile push (FCM) deferred to post-V1. 
