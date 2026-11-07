"""
Daily Hadith AI Agent — Telegram Webhook Management CLI.

Utility script to inspect, configure, and delete the inbound Telegram webhook
for cloud deployments (e.g., Render, Google Cloud Run).

Usage:
    # Query current webhook status:
    python -m scripts.register_webhook --info

    # Register webhook for a public cloud deployment:
    python -m scripts.register_webhook --set https://your-app.onrender.com/telegram/webhook

    # Delete existing webhook:
    python -m scripts.register_webhook --delete
"""

import argparse
import json
import logging
import sys

from src.config import get_settings
from src.delivery.telegram import TelegramClient, TelegramDeliveryError

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("register_webhook")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Telegram Webhook Management CLI for Daily Hadith AI Agent.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--set",
        metavar="URL",
        help="Full public HTTPS URL to register for Telegram webhooks (e.g. https://domain.com/telegram/webhook).",
    )
    group.add_argument(
        "--info",
        action="store_true",
        help="Query and print current Telegram webhook configuration and pending update count.",
    )
    group.add_argument(
        "--delete",
        action="store_true",
        help="Remove active webhook from Telegram Bot API.",
    )

    parser.add_argument(
        "--drop-pending",
        action="store_true",
        default=False,
        help="Drop all accumulated pending updates upon webhook modification.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()

    if not settings.telegram_bot_token:
        logger.error(
            "TELEGRAM_BOT_TOKEN is not configured in environment or .env. Cannot authenticate with Telegram."
        )
        return 1

    adapter = TelegramClient(settings=settings)

    try:
        if args.info:
            logger.info("Querying current Telegram webhook configuration...")
            info = adapter.get_webhook_info()
            print("\n=== Telegram Webhook Status ===")
            print(json.dumps(info, indent=2, ensure_ascii=False))
            print("===============================\n")
            if info.get("url"):
                logger.info("Webhook is ACTIVE and pointing to: %s", info["url"])
            else:
                logger.info(
                    "No active webhook configured (bot is in polling mode or unconfigured)."
                )
            return 0

        elif args.set:
            url = args.set.strip()
            if not url.startswith("https://"):
                logger.error("Telegram webhooks REQUIRE an HTTPS URL (got: %s).", url)
                return 1

            secret_token = settings.telegram_webhook_secret_token
            logger.info("Registering Telegram webhook: %s", url)
            if secret_token:
                logger.info("Attaching constant-time secret token header verification.")
            else:
                logger.warning(
                    "TELEGRAM_WEBHOOK_SECRET_TOKEN is not set; webhook will not verify origin secret header."
                )

            res = adapter.set_webhook(
                url=url,
                secret_token=secret_token,
                drop_pending_updates=args.drop_pending,
            )
            logger.info("Webhook registration successful! Result: %s", res)
            return 0

        elif args.delete:
            logger.info("Deleting Telegram webhook...")
            res = adapter.delete_webhook(drop_pending_updates=args.drop_pending)
            logger.info("Webhook deleted successfully! Result: %s", res)
            return 0

    except TelegramDeliveryError as exc:
        logger.error("Telegram API error: %s", exc)
        return 1
    except Exception as exc:
        logger.exception("Unexpected error executing webhook CLI: %s", exc)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
