# Production Operational Runbook

Operational and maintenance procedures for the **Daily Hadith AI Agent** production system.

---

## 1. System Topology & Production URLs

| Component | Production Service | Public URL / Endpoint |
|---|---|---|
| **Web Service & Webhook** | Render Free Web Service (Python 3) | `https://daily-hadith-ai-agent-46ie.onrender.com` |
| **Health Probe** | FastAPI HTTP GET/POST/HEAD | `https://daily-hadith-ai-agent-46ie.onrender.com/health` |
| **Telegram Inbound Webhook** | FastAPI HTTP POST | `https://daily-hadith-ai-agent-46ie.onrender.com/telegram/webhook` |
| **Cloud Scheduler Trigger** | Authenticated HTTP POST | `https://daily-hadith-ai-agent-46ie.onrender.com/api/cron/daily-broadcast` |
| **PostgreSQL Database** | Neon Serverless PostgreSQL (SSL) | `ep-calm-cloud-b8sdiz8h-pooler.c-14.us-east-1.aws.neon.tech` |
| **Container Registry** | Docker Hub (Multi-Stage) | `hub.docker.com/r/amankhan1009/daily-hadith-ai-agent` |
| **Automated Cron Scheduler** | GitHub Actions Workflow | Daily at `04:25 UTC` (`09:55 AM IST`) + fallback `04:35 UTC` (`10:05 AM IST`) via `.github/workflows/hadith-broadcast.yml` |

---

## 2. Health Check & Live Monitoring

### 2.1 Basic Liveness Probe
```bash
curl -i https://daily-hadith-ai-agent.onrender.com/health
```
**Expected Response (HTTP 200 OK):**
```json
{
  "status": "healthy",
  "service": "daily-hadith-ai-agent",
  "environment": "production",
  "timezone": "Asia/Kolkata",
  "scheduler": {
    "running": false,
    "next_run_time": null
  }
}
```

### 2.2 Telegram Webhook Status Inspection
To inspect the live webhook configuration directly with Telegram Bot API:
```bash
.venv/bin/python -m scripts.register_webhook --info
```
**Expected Output:**
```json
{
  "url": "https://daily-hadith-ai-agent.onrender.com/telegram/webhook",
  "has_custom_certificate": false,
  "pending_update_count": 0,
  "max_connections": 40
}
```

---

## 3. Standard Operational Procedures (SOPs)

### 3.1 Ingesting & Backfilling Candidate Hadiths
To pre-load new verified Hadiths into the Neon PostgreSQL candidate queue:
```bash
# Ingest category 5 (Virtues and Manners), page 1 (20 items)
.venv/bin/python -c "
from src.database.session import get_db_session
from src.ingestion.service import CandidateIngestionService

with get_db_session() as session:
    service = CandidateIngestionService()
    summary = service.ingest_category_batch(session, category_id=5, page=1, per_page=20)
    print(f'Batch Ingestion Summary: {summary}')
"
```

### 3.2 Triggering a Manual Daily Broadcast (CLI)
To manually execute or dry-run the daily delivery pipeline:
```bash
# Dry run mode (generates reflection and tests routing without sending Telegram messages)
.venv/bin/python -m src.workflow.daily_runner --dry-run

# Live delivery for today's date (Asia/Kolkata)
.venv/bin/python -m src.workflow.daily_runner

# Live delivery for a specific date (backfill or test)
.venv/bin/python -m src.workflow.daily_runner --date 2026-11-08
```

### 3.3 Triggering the Cloud Scheduler Endpoint via HTTP
To trigger the broadcast remotely via curl (simulating cron-job.org):
```bash
curl -X POST https://daily-hadith-ai-agent.onrender.com/api/cron/daily-broadcast \
  -H "X-Cron-Secret: <YOUR_CRON_SECRET_TOKEN>"
```

---

## 4. Secret & Credential Rotation Runbooks

### 4.1 Rotating `TELEGRAM_BOT_TOKEN`
1. Open `@BotFather` on Telegram and send `/token`.
2. Choose the bot and select **Revoke current token**. Copy the new token.
3. Update `TELEGRAM_BOT_TOKEN` in Render Dashboard under **Environment**.
4. Update local `.env`.
5. Re-register the webhook with the new token:
   ```bash
   .venv/bin/python -m scripts.register_webhook --set https://daily-hadith-ai-agent.onrender.com/telegram/webhook
   ```

### 4.2 Rotating `TELEGRAM_WEBHOOK_SECRET_TOKEN`
1. Generate a new 32-character random hex string:
   ```bash
   python3 -c "import secrets; print(secrets.token_hex(16))"
   ```
2. Update `TELEGRAM_WEBHOOK_SECRET_TOKEN` in Render Dashboard.
3. Update local `.env`.
4. Run the registration CLI to update Telegram with the new secret:
   ```bash
   .venv/bin/python -m scripts.register_webhook --set https://daily-hadith-ai-agent.onrender.com/telegram/webhook
   ```

### 4.3 Rotating `CRON_SECRET_TOKEN`
1. Generate a new secret token:
   ```bash
   python3 -c "import secrets; print(secrets.token_hex(16))"
   ```
2. Update `CRON_SECRET_TOKEN` in Render Dashboard.
3. Update header `X-Cron-Secret` in **cron-job.org** console.
4. Update local `.env`.

---

## 5. Disaster Recovery & Failure Mitigations

| Failure Mode | Detection | Automated System Response | Operator Remediation |
|---|---|---|---|
| **HadeethEnc Upstream Outage** | Ingestion raises `HadeethEncNetworkError` or `HadeethEncResponseError` | Ingestion aborts fail-closed; candidate queue is not corrupted. | None required; existing verified candidates in Neon PostgreSQL continue to serve daily broadcasts. |
| **Groq Cloud Outage or Rate Limit** | `GroqReflectionClient` receives HTTP 429 or 500 | System gracefully omits AI reflection (`ai_reflection=None`, status=`FAILED`); delivers authentic Hadith alone without disruption. | Monitor Groq service status; pipeline auto-recovers on next run. |
| **Theological Guardrail Violation** | `validate_guardrails_node` detects decree or unauthorized citation | Omits AI reflection with status `OMITTED_GUARDRAIL_FAILED`; logs warning; delivers pure Hadith text. | Audit candidate in database; system safely protected subscribers from non-canonical content. |
| **Subscriber Blocks Bot (HTTP 403)** | Telegram returns HTTP 403 Forbidden on dispatch | System catches `TelegramBotBlockedError`, immediately sets subscriber `is_active=False` in Neon DB. | None required; subscriber is excluded from future fan-outs until they re-issue `/start`. |
| **Telegram Rate Limit (HTTP 429)** | Telegram API returns HTTP 429 Retry-After | Client sleeps for `retry_after + 1.0` seconds and retries up to 3 times with exponential backoff. | System operates at 30 msg/sec throttled limit to prevent 429 triggers. |
| **Duplicate Daily Broadcast Trigger** | Cron scheduler sends multiple trigger requests | Database unique constraint on `daily_delivery_logs.scheduled_date` prevents duplicate runs; StateGraph skips execution. | Safe by design; no duplicate messages are dispatched to users. |
| **Neon PostgreSQL Connection Drops** | Driver throws `OperationalError` on checkout | SQLAlchemy connection pooler uses `pool_pre_ping=True` to recycle broken connections transparently. | Verify Neon console status and database connection string. |
