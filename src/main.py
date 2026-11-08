"""
Daily Hadith AI Agent — Main FastAPI Application.

Serves healthchecks, inbound Telegram webhooks, and authenticated Cloud Scheduler
triggers for daily Hadith broadcasts.
"""

import hmac
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Header, HTTPException, status
from fastapi.responses import HTMLResponse

from src.config import get_settings
from src.delivery import webhook_router
from src.workflow.daily_runner import run_daily_broadcast
from src.workflow.scheduler import (
    get_scheduler_status,
    shutdown_daily_scheduler,
    start_daily_scheduler,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan managing background scheduler startup and shutdown."""
    settings = get_settings()
    if settings.enable_in_process_scheduler:
        logger.info("In-process scheduler enabled by configuration. Starting...")
        start_daily_scheduler()
    yield
    if settings.enable_in_process_scheduler:
        shutdown_daily_scheduler()


def create_app() -> FastAPI:
    """FastAPI application factory."""
    settings = get_settings()

    app = FastAPI(
        title="Daily Hadith AI Agent",
        description="Public Telegram bot and automated daily Hadith broadcast engine.",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Mount Telegram inbound webhook router (/telegram/webhook)
    app.include_router(webhook_router)

    @app.get("/", response_class=HTMLResponse, tags=["System"])
    def home() -> str:
        """Public landing page displaying bot status and navigation links."""
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Daily Hadith AI Agent — Production Status</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220%22><text y=%2226%22 font-size=%2224%22>📖</text></svg>">
    <style>
        :root {
            --bg: #090d16;
            --card-bg: rgba(17, 24, 39, 0.7);
            --border: rgba(255, 255, 255, 0.08);
            --primary: #10b981;
            --primary-glow: rgba(16, 185, 129, 0.25);
            --text-main: #f3f4f6;
            --text-muted: #9ca3af;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: radial-gradient(circle at 50% 0%, #132338 0%, var(--bg) 75%);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 24px;
        }
        .container {
            max-width: 620px;
            width: 100%;
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 20px;
            padding: 44px 36px;
            backdrop-filter: blur(16px);
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.6);
            text-align: center;
        }
        .badge {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 6px 14px;
            background: rgba(16, 185, 129, 0.12);
            border: 1px solid rgba(16, 185, 129, 0.3);
            border-radius: 9999px;
            font-size: 13px;
            font-weight: 600;
            color: var(--primary);
            margin-bottom: 24px;
        }
        .pulse-dot {
            width: 8px;
            height: 8px;
            background: var(--primary);
            border-radius: 50%;
            box-shadow: 0 0 10px var(--primary);
        }
        h1 {
            font-size: 30px;
            font-weight: 700;
            letter-spacing: -0.5px;
            margin-bottom: 12px;
            background: linear-gradient(135deg, #ffffff 30%, #a7f3d0 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        p.subtitle {
            font-size: 15px;
            line-height: 1.6;
            color: var(--text-muted);
            margin-bottom: 32px;
        }
        .btn-group {
            display: flex;
            flex-direction: column;
            gap: 12px;
            margin-bottom: 32px;
        }
        @media(min-width: 480px) {
            .btn-group { flex-direction: row; justify-content: center; }
        }
        .btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            padding: 13px 22px;
            border-radius: 12px;
            font-size: 14px;
            font-weight: 600;
            text-decoration: none;
            transition: all 0.2s ease;
        }
        .btn-primary {
            background: var(--primary);
            color: #064e3b;
            box-shadow: 0 4px 14px var(--primary-glow);
        }
        .btn-primary:hover {
            transform: translateY(-2px);
            background: #34d399;
        }
        .btn-secondary {
            background: rgba(255, 255, 255, 0.05);
            color: var(--text-main);
            border: 1px solid var(--border);
        }
        .btn-secondary:hover {
            background: rgba(255, 255, 255, 0.1);
            transform: translateY(-2px);
        }
        .meta-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 12px;
            border-top: 1px solid var(--border);
            padding-top: 24px;
        }
        .meta-item {
            text-align: center;
        }
        .meta-label {
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-muted);
            margin-bottom: 4px;
        }
        .meta-value {
            font-size: 13px;
            font-weight: 600;
            color: var(--text-main);
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="badge">
            <span class="pulse-dot"></span>
            System Active & Live
        </div>
        <h1>Daily Hadith Agent</h1>
        <p class="subtitle">
            A production-grade, fail-closed AI system delivering authentic Hadith from Sahih al-Bukhari & Muslim paired with educational commentary.
        </p>
        <div class="btn-group">
            <a href="https://t.me/daily_hadith_aman_bot" target="_blank" class="btn btn-primary">
                💬 Open in Telegram
            </a>
            <a href="/docs" class="btn btn-secondary">
                ⚡ API Documentation
            </a>
            <a href="/health" class="btn btn-secondary">
                🩺 Health Probe
            </a>
        </div>
        <div class="meta-grid">
            <div class="meta-item">
                <div class="meta-label">Schedule</div>
                <div class="meta-value">10:00 AM IST</div>
            </div>
            <div class="meta-item">
                <div class="meta-label">Orchestrator</div>
                <div class="meta-value">LangGraph</div>
            </div>
            <div class="meta-item">
                <div class="meta-label">Database</div>
                <div class="meta-value">Neon PostgreSQL</div>
            </div>
        </div>
    </div>
</body>
</html>"""

    @app.get("/health", tags=["System"])
    def health_check() -> dict[str, Any]:
        """Container healthcheck endpoint for Docker, Cloud Run, and Render."""
        return {
            "status": "healthy",
            "service": "daily-hadith-ai-agent",
            "environment": settings.app_env,
            "timezone": settings.timezone,
            "scheduler": get_scheduler_status(),
        }

    @app.post("/api/cron/daily-broadcast", tags=["Cloud Scheduler"])
    def trigger_cron_broadcast(
        x_cron_secret: str | None = Header(None),
        authorization: str | None = Header(None),
    ) -> dict[str, Any]:
        """
        Authenticated trigger endpoint for Google Cloud Scheduler or external cron services.
        Validates X-Cron-Secret header or Bearer token before running the broadcast.
        """
        configured_secret = settings.cron_secret_token
        if configured_secret:
            incoming_token = x_cron_secret
            if not incoming_token and authorization and authorization.startswith("Bearer "):
                incoming_token = authorization.split("Bearer ", 1)[1].strip()

            if not incoming_token or not hmac.compare_digest(incoming_token, configured_secret):
                logger.warning("Rejected unauthorized call to /api/cron/daily-broadcast")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: Invalid cron secret token",
                )

        logger.info("Executing daily broadcast triggered via /api/cron/daily-broadcast")
        final_state = run_daily_broadcast()
        return {
            "ok": final_state.get("status") in ("COMPLETED", "SKIPPED_IDEMPOTENT"),
            "status": final_state.get("status"),
            "scheduled_date": final_state.get("scheduled_date"),
            "candidate_id": final_state.get("candidate_id"),
            "delivered_count": final_state.get("delivered_count", 0),
        }

    return app


app = create_app()
