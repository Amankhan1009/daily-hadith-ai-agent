"""
Headless Daily Hadith Broadcast Runner CLI.

Entrypoint for Google Cloud Run Jobs, cron triggers, and manual CLI executions.
Calculates Asia/Kolkata target date, executes LangGraph StateGraph, logs
execution metrics, and sets exit codes.
"""

import argparse
import logging
import sys
from typing import Any, Optional
from unittest.mock import MagicMock

from src.config import get_settings
from src.delivery import TelegramClient
from src.workflow.graph import run_daily_workflow
from src.workflow.state import get_current_ist_date

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("daily_runner")


def run_daily_broadcast(
    target_date: Optional[str] = None,
    dry_run: bool = False,
    telegram_client: Optional[TelegramClient] = None,
) -> dict[str, Any]:
    """
    Execute daily broadcast workflow for target date with structured logging.

    Args:
        target_date: ISO date string (YYYY-MM-DD), defaults to current date in Asia/Kolkata.
        dry_run: If True, simulates Telegram delivery without dispatching actual messages.
        telegram_client: Optional injected TelegramClient adapter.

    Returns:
        dict[str, Any]: Final workflow execution state.
    """
    settings = get_settings()
    scheduled_date = target_date or get_current_ist_date()

    logger.info("=" * 65)
    logger.info("🚀 INITIATING DAILY HADITH BROADCAST RUNNER")
    logger.info("=" * 65)
    logger.info("• Target Scheduled Date (IST): %s", scheduled_date)
    logger.info("• Execution Timezone: %s", settings.timezone)
    logger.info("• Dry Run Mode: %s", "ENABLED (simulated dispatch)" if dry_run else "DISABLED (live dispatch)")

    # In dry-run mode, simulate delivery without calling Telegram Bot API
    if dry_run and telegram_client is None:
        mock_client = MagicMock(spec=TelegramClient)
        mock_client.bot_token = "DRY_RUN_TOKEN"
        mock_client.send_message.return_value = {"message_id": 99999, "simulated": True}
        telegram_client = mock_client

    final_state = run_daily_workflow(
        scheduled_date=scheduled_date,
        telegram_client=telegram_client,
    )

    status = final_state.get("status", "UNKNOWN")
    logger.info("-" * 65)
    logger.info("📊 WORKFLOW EXECUTION SUMMARY")
    logger.info("-" * 65)
    logger.info("• Final Status: %s", status)
    logger.info("• Candidate ID: %s", final_state.get("candidate_id"))
    logger.info("• Collection: %s (#%s)", final_state.get("collection"), final_state.get("hadith_number"))
    logger.info("• AI Reflection Status: %s", final_state.get("ai_reflection_status"))
    logger.info("• Total Active Subscribers: %s", final_state.get("subscribers_count", 0))
    logger.info("• Successfully Delivered: %s", final_state.get("delivered_count", 0))
    logger.info("• Failed / Blocked: %s", final_state.get("failed_count", 0))

    if final_state.get("error_message"):
        logger.warning("• Diagnostic Message: %s", final_state.get("error_message"))

    logger.info("=" * 65)
    return final_state


def main() -> None:
    """CLI argument parser and entrypoint."""
    parser = argparse.ArgumentParser(description="Daily Hadith AI Agent — Daily Broadcast Runner")
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Target delivery date in YYYY-MM-DD format (defaults to current Asia/Kolkata date)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate run without dispatching actual messages to Telegram",
    )
    args = parser.parse_args()

    state = run_daily_broadcast(target_date=args.date, dry_run=args.dry_run)
    status = state.get("status")

    # Exit code 0 for success and idempotent skip; 1 for operational failures
    if status in ("COMPLETED", "SKIPPED_IDEMPOTENT"):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()