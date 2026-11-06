# Delivery Package (`src/delivery`)

The `src/delivery` package provides outbound Telegram notification delivery and handles inbound webhook interactions for the public Daily Hadith AI Agent bot.

---

## Key Modules

| Module | Primary Responsibility |
|---|---|
| **[`telegram.py`](telegram.py)** | Resilient `TelegramClient` adapter for the official Telegram Bot API with exponential backoff, HTTP 429 rate limit backoff, and HTTP 403 bot-blocked detection. |
| **[`router.py`](router.py)** | FastAPI router mounting `POST /telegram/webhook`, verifying `X-Telegram-Bot-Api-Secret-Token`, and dispatching public bot commands (`/start`, `/today`, `/stop`, `/help`). |

---

## Public Bot Commands

- **`/start`**: Idempotently registers or reactivates subscriber (`is_active = True`), sends welcome onboarding message, and dispatches today's verified Hadith immediately.
- **`/today`**: On-demand query to fetch and deliver the current verified Hadith.
- **`/stop`**: Opts out subscriber gracefully (`is_active = False`) and confirms unsubscribe status.
- **`/help`**: Outlines available commands, theological boundaries (zero AI modification of Hadith text), and HadeethEnc source attribution.

---

## Webhook Security

Incoming webhook calls must include the HTTP header:
```http
X-Telegram-Bot-Api-Secret-Token: <configured_token>
```
If missing, invalid, or forged, the endpoint rejects the request with HTTP `403 Forbidden` using constant-time comparison (`hmac.compare_digest`).

---

## Rate Limiting & Error Recovery

- **Broadcast Rate Limiting**: The multi-user fan-out broadcaster caps outbound messages at 25 msgs/second to remain safely below Telegram's 30 msgs/second broadcast ceiling.
- **Bot Block Auto-Deactivation**: If Telegram returns HTTP `403 Forbidden` (user deleted or blocked the bot), the delivery engine immediately marks `TelegramSubscriber.is_active = False` in Neon PostgreSQL.