"""
Database Package Public Exports.
"""

from src.database.models import (
    DailyDeliveryLog,
    HadithCandidate,
    SubscriberDeliveryLog,
    TelegramSubscriber,
)
from src.database.repository import (
    deactivate_subscriber,
    get_active_subscribers,
    get_candidate_by_source_id,
    get_next_verified_candidate,
    get_or_create_subscriber,
    get_subscriber_by_chat_id,
    get_undelivered_active_subscribers,
    is_date_delivered,
    is_delivery_recorded,
    is_subscriber_delivered,
    record_delivery_log,
    record_subscriber_delivery,
    save_candidate,
)
from src.database.session import Base, engine, get_db_session, init_db

__all__ = [
    "Base",
    "DailyDeliveryLog",
    "HadithCandidate",
    "SubscriberDeliveryLog",
    "TelegramSubscriber",
    "deactivate_subscriber",
    "engine",
    "get_active_subscribers",
    "get_candidate_by_source_id",
    "get_db_session",
    "get_next_verified_candidate",
    "get_or_create_subscriber",
    "get_subscriber_by_chat_id",
    "get_undelivered_active_subscribers",
    "init_db",
    "is_date_delivered",
    "is_delivery_recorded",
    "is_subscriber_delivered",
    "record_delivery_log",
    "record_subscriber_delivery",
    "save_candidate",
]
