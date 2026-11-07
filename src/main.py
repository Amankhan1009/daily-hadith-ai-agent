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
