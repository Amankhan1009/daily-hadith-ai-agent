"""
Database Package Public Exports.
"""

from src.database.models import DailyDeliveryLog, HadithCandidate, TelegramSubscriber
from src.database.repository import (
    deactivate_subscriber,
    get_active_subscribers,
    get_candidate_by_source_id,
    get_next_verified_candidate,
    get_or_create_subscriber,
    get_subscriber_by_chat_id,
    is_date_delivered,
    is_delivery_recorded,
    record_delivery_log,
    save_candidate,
)
from src.database.session import Base, engine, get_db_session, init_db

__all__ = [
    "Base",
    "DailyDeliveryLog",
    "HadithCandidate",
    "engine",
    "get_candidate_by_source_id",
    "get_db_session",
    "get_next_verified_candidate",
    "init_db",
    "is_date_delivered",
    "record_delivery_log",
    "save_candidate",
    "SubscriberDeliveryLog",
    "get_undelivered_active_subscribers",
    "record_subscriber_delivery",
    "is_subscriber_delivered",
]
