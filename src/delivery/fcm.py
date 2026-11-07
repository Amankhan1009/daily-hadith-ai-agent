"""
Daily Hadith AI Agent — Firebase Cloud Messaging (FCM) Integration Adapter.

Provides typed Pydantic models for FCM v1 REST payloads, payload size boundary
enforcement (4KB limit), and multi-channel notification dispatch interfaces.
Part of Milestone 20 Architectural Evaluation.
"""

import json
import logging
from typing import Any

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

# Strict 4KB boundary mandated by Google Firebase Cloud Messaging v1 API
MAX_FCM_PAYLOAD_BYTES = 4096


class FCMDataPayload(BaseModel):
    """Structured data payload embedded in FCM push notification for deep-linking."""

    candidate_id: str
    collection: str
    hadith_number: str
    grade: str
    source_url: str
    scheduled_date: str
    has_reflection: str = "false"
    click_action: str = "FLUTTER_NOTIFICATION_CLICK"


class FCMNotificationMessage(BaseModel):
    """Visible lock-screen notification display contents."""

    title: str = Field(..., max_length=120, description="Headline title for notification tray")
    body: str = Field(..., max_length=500, description="Concise teaser preview of the Hadith")


class FCMPushPayload(BaseModel):
    """
    Standardized payload for Google Firebase Cloud Messaging (FCM) v1 API.
    Enforces the 4,096-byte payload constraint and constructs valid JSON specifications.
    """

    target: str = Field(
        ...,
        description="FCM Registration Token (device) or Topic name (e.g. /topics/daily_hadith)",
    )
    is_topic: bool = Field(default=False)
    notification: FCMNotificationMessage
    data: FCMDataPayload

    @field_validator("target")
    @classmethod
    def validate_target_format(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("FCM target token or topic cannot be empty.")
        return clean

    def to_fcm_message_dict(self) -> dict[str, Any]:
        """Convert to official Google FCM v1 HTTP API message body dictionary."""
        target_key = "topic" if self.is_topic else "token"
        clean_target = self.target.removeprefix("/topics/") if self.is_topic else self.target

        message: dict[str, Any] = {
            target_key: clean_target,
            "notification": self.notification.model_dump(),
            "data": self.data.model_dump(),
            "android": {
                "priority": "high",
                "notification": {
                    "channel_id": "daily_hadith_channel",
                    "icon": "ic_hadith_notification",
                    "color": "#064e3b",
                },
            },
            "apns": {
                "payload": {
                    "aps": {
                        "alert": {
                            "title": self.notification.title,
                            "body": self.notification.body,
                        },
                        "badge": 1,
                        "sound": "default",
                    }
                }
            },
        }

        # Validate total serialized JSON size against 4KB limit
        serialized = json.dumps({"message": message})
        payload_bytes = len(serialized.encode("utf-8"))
        if payload_bytes > MAX_FCM_PAYLOAD_BYTES:
            raise ValueError(
                f"FCM payload exceeds 4KB limit ({payload_bytes} bytes > {MAX_FCM_PAYLOAD_BYTES} bytes)."
            )

        return {"message": message}


class FCMDeliveryAdapter:
    """
    Adapter client managing push delivery to Google Firebase Cloud Messaging.
    Supports mock/dry-run execution and real firebase-admin dispatch.
    """

    def __init__(self, dry_run: bool = True) -> None:
        self.dry_run = dry_run

    def send_notification(self, payload: FCMPushPayload) -> dict[str, Any]:
        """
        Dispatch notification payload to an individual device token or topic.
        In dry-run mode, validates schemas and payload constraints without network I/O.
        """
        message_dict = payload.to_fcm_message_dict()

        if self.dry_run:
            logger.info(
                "FCM dry-run dispatch verified for target '%s' (payload size: %d bytes)",
                payload.target,
                len(json.dumps(message_dict).encode("utf-8")),
            )
            return {
                "success": True,
                "mode": "dry_run",
                "message_id": f"projects/daily-hadith/messages/mock_{payload.data.candidate_id}",
                "target": payload.target,
            }

        # Production firebase-admin SDK dispatch hook
        raise NotImplementedError("Live firebase-admin SDK dispatch reserved for V2 rollout.")
