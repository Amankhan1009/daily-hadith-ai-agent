"""
In-Process Application Scheduler.

Provides background job scheduling strictly locked to Asia/Kolkata timezone
with 1-hour misfire grace time to guarantee execution after server restarts.
"""

import logging
from typing import Any
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from src.config import get_settings
from src.workflow.daily_runner import run_daily_broadcast

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None
JOB_ID = "daily_hadith_broadcast"


def create_daily_scheduler() -> BackgroundScheduler:
    """
    Construct a BackgroundScheduler configured for Asia/Kolkata at 10:00 AM IST.
    Enforces a 3600-second (1-hour) misfire grace time to catch missed runs.
    """
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)

    scheduler = BackgroundScheduler(timezone=tz)

    # Trigger at 10:00 AM IST every day
    trigger = CronTrigger(
        hour=10,
        minute=0,
        timezone=tz,
    )

    scheduler.add_job(
        func=run_daily_broadcast,
        trigger=trigger,
        id=JOB_ID,
        name="Daily Hadith Broadcast (10:00 AM IST)",
        misfire_grace_time=3600,  # 1 hour grace time for server reboots
        coalesce=True,  # Combine multiple missed runs into single run
        max_instances=1,  # Prevent overlapping executions
        replace_existing=True,
    )

    return scheduler


def start_daily_scheduler() -> BackgroundScheduler:
    """Initialize and start the global background scheduler if not already running."""
    global _scheduler
    if _scheduler is None or not _scheduler.running:
        _scheduler = create_daily_scheduler()
        _scheduler.start()
        logger.info("Daily broadcast background scheduler started (Asia/Kolkata 10:00 AM).")
    return _scheduler


def shutdown_daily_scheduler() -> None:
    """Gracefully stop the background scheduler."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Daily broadcast background scheduler stopped.")
    _scheduler = None


def get_scheduler_status() -> dict[str, Any]:
    """Retrieve diagnostic health status and next scheduled run time."""
    global _scheduler
    if _scheduler is None or not _scheduler.running:
        return {"running": False, "next_run_time": None}

    job = _scheduler.get_job(JOB_ID)
    next_run = job.next_run_time.isoformat() if job and job.next_run_time else None
    return {
        "running": True,
        "job_id": JOB_ID,
        "next_run_time": next_run,
        "timezone": str(_scheduler.timezone),
    }
