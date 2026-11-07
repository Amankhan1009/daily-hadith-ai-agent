"""
Automated Architectural Evaluation Tests for Future FCM Integration (Milestone 20).

Verifies:
1. Valid FCM notification and data payload construction.
2. Official FCM v1 REST dictionary formatting (Android, APNs, Notification, Data).
3. Topic broadcast formatting (/topics/daily_hadith).
4. Strict 4,096-byte (4KB) payload boundary enforcement.
5. Adapter dry-run execution and error handling.
"""

import pytest

from src.delivery.fcm import (
    FCMDataPayload,
    FCMDeliveryAdapter,
    FCMNotificationMessage,
    FCMPushPayload,
)


@pytest.fixture
def sample_fcm_data():
    return FCMDataPayload(
        candidate_id="66521",
        collection="Sahih Muslim",
        hadith_number="1955",
        grade="Authentic",
        source_url="https://hadeethenc.com/en/browse/hadith/66521",
        scheduled_date="2026-11-08",
        has_reflection="true",
    )


@pytest.fixture
def sample_fcm_notification():
    return FCMNotificationMessage(
        title="Hadith of the Day — Sahih Muslim (#1955)",
        body="Indeed, Allah has enjoined Ihsan (kindness/excellence) in all things...",
    )


def test_fcm_payload_valid_device_token(sample_fcm_data, sample_fcm_notification):
    """Verify valid FCM device token payload builds compliant v1 dictionary."""
    payload = FCMPushPayload(
        target="fcm_device_token_xyz_12345",
        is_topic=False,
        notification=sample_fcm_notification,
        data=sample_fcm_data,
    )

    msg_dict = payload.to_fcm_message_dict()

    assert "message" in msg_dict
    msg = msg_dict["message"]
    assert msg["token"] == "fcm_device_token_xyz_12345"
    assert "topic" not in msg
    assert msg["notification"]["title"] == "Hadith of the Day — Sahih Muslim (#1955)"
    assert msg["data"]["candidate_id"] == "66521"
    assert msg["android"]["priority"] == "high"
    assert msg["apns"]["payload"]["aps"]["sound"] == "default"


def test_fcm_payload_valid_topic_broadcast(sample_fcm_data, sample_fcm_notification):
    """Verify valid FCM topic broadcast builds compliant topic message."""
    payload = FCMPushPayload(
        target="/topics/daily_hadith_ist",
        is_topic=True,
        notification=sample_fcm_notification,
        data=sample_fcm_data,
    )

    msg_dict = payload.to_fcm_message_dict()

    assert "message" in msg_dict
    msg = msg_dict["message"]
    assert msg["topic"] == "daily_hadith_ist"
    assert "token" not in msg


def test_fcm_payload_empty_target_raises_value_error(sample_fcm_data, sample_fcm_notification):
    """Verify empty target token or topic raises validation error."""
    with pytest.raises(ValueError, match="FCM target token or topic cannot be empty"):
        FCMPushPayload(
            target="   ",
            is_topic=False,
            notification=sample_fcm_notification,
            data=sample_fcm_data,
        )


def test_fcm_payload_exceeding_4kb_raises_value_error(sample_fcm_data, sample_fcm_notification):
    """Verify payload exceeding the 4,096-byte boundary fails closed."""
    # Inject oversized string into data payload to exceed 4KB
    oversized_data = sample_fcm_data.model_copy(update={"click_action": "X" * 4500})

    payload = FCMPushPayload(
        target="token_123",
        is_topic=False,
        notification=sample_fcm_notification,
        data=oversized_data,
    )

    with pytest.raises(ValueError, match="FCM payload exceeds 4KB limit"):
        payload.to_fcm_message_dict()


def test_fcm_adapter_dry_run_dispatch(sample_fcm_data, sample_fcm_notification):
    """Verify dry-run dispatch validates payload and returns mock message identifier."""
    adapter = FCMDeliveryAdapter(dry_run=True)
    payload = FCMPushPayload(
        target="token_test_abc",
        is_topic=False,
        notification=sample_fcm_notification,
        data=sample_fcm_data,
    )

    result = adapter.send_notification(payload)

    assert result["success"] is True
    assert result["mode"] == "dry_run"
    assert "mock_66521" in result["message_id"]
