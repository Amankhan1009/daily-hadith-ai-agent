"""
Database ORM Table Models.

Defines schemas for candidate records, reference metadata, AI reflection
status, and idempotent daily delivery tracking.
"""

from datetime import UTC, date, datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.session import Base


def utc_now() -> datetime:
    """Return the current timestamp in UTC timezone."""
    return datetime.now(UTC)


class HadithCandidate(Base):
    """
    Stores retrieved Hadith candidates, verified provenance, and AI reflection status.
    """

    __tablename__ = "hadith_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(
        String(64), index=True, nullable=False, doc="HadeethEnc Record ID"
    )
    collection: Mapped[str] = mapped_column(
        String(128), index=True, nullable=False, doc="Verified collection name"
    )
    hadith_number: Mapped[str | None] = mapped_column(
        String(64), nullable=True, doc="Extracted Hadith reference number"
    )

    english_title: Mapped[str] = mapped_column(String(512), nullable=False)
    english_text: Mapped[str] = mapped_column(
        Text, nullable=False, doc="Canonical unchanged English translation"
    )
    arabic_text: Mapped[str] = mapped_column(
        Text, nullable=False, doc="Canonical verified Arabic text"
    )
    attribution: Mapped[str] = mapped_column(
        String(256), nullable=False, doc="e.g. Narrated by Al-Bukhari"
    )
    grade: Mapped[str] = mapped_column(String(256), nullable=False, doc="e.g. Authentic / Sahih")
    source_url: Mapped[str] = mapped_column(
        String(512), nullable=False, doc="Canonical HadeethEnc browse URL"
    )
    translation_version: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Segregated AI Reflection fields
    ai_reflection: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="Separately labeled AI commentary"
    )
    ai_reflection_status: Mapped[str] = mapped_column(
        String(32),
        default="NOT_GENERATED",
        nullable=False,
        doc="NOT_GENERATED | GENERATED | OMITTED | FAILED",
    )

    # Verification Lifecycle
    verification_status: Mapped[str] = mapped_column(
        String(32),
        default="PENDING",
        index=True,
        nullable=False,
        doc="PENDING | VERIFIED | REJECTED | DELIVERED",
    )
    rejection_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    delivery_logs: Mapped[list["DailyDeliveryLog"]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
    )


class DailyDeliveryLog(Base):
    """
    Audit log enforcing daily delivery idempotency and tracking dispatch outcomes.
    """

    __tablename__ = "daily_delivery_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scheduled_date: Mapped[date] = mapped_column(
        Date,
        unique=True,
        index=True,
        nullable=False,
        doc="Calendar delivery date enforcing strict exactly-once daily dispatch",
    )
    candidate_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("hadith_candidates.id", ondelete="SET NULL"),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        default="PENDING",
        index=True,
        nullable=False,
        doc="PENDING | SUCCESS | FAILED | SKIPPED",
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    telegram_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    candidate: Mapped[Optional["HadithCandidate"]] = relationship(back_populates="delivery_logs")


class TelegramSubscriber(Base):
    """
    Subscribers registered via public Telegram /start for daily Hadith notifications.
    """

    __tablename__ = "telegram_subscribers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        index=True,
        nullable=False,
        doc="Telegram unique 64-bit chat ID",
    )
    username: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Telegram @username without symbol",
    )
    first_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Telegram user first name",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        index=True,
        nullable=False,
        doc="Subscription status: True if opted in, False if opted out via /stop or blocked",
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        doc="Initial subscription registration timestamp",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
        doc="Timestamp of latest command interaction or status change",
    )
    # Relationships
    delivery_logs: Mapped[list["SubscriberDeliveryLog"]] = relationship(
        back_populates="subscriber",
        cascade="all, delete-orphan",
    )


class SubscriberDeliveryLog(Base):
    """
    Per-subscriber delivery log enforcing strictly exactly-once delivery per calendar day
    via a composite unique constraint on (subscriber_id, scheduled_date).
    """

    __tablename__ = "subscriber_delivery_logs"
    __table_args__ = (
        UniqueConstraint("subscriber_id", "scheduled_date", name="uq_subscriber_daily_delivery"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subscriber_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("telegram_subscribers.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    chat_id: Mapped[int] = mapped_column(
        BigInteger,
        index=True,
        nullable=False,
        doc="Denormalized Telegram chat ID for direct lookup",
    )
    scheduled_date: Mapped[date] = mapped_column(
        Date,
        index=True,
        nullable=False,
        doc="Calendar delivery date enforcing per-subscriber daily idempotency",
    )
    candidate_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("hadith_candidates.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="PENDING",
        index=True,
        nullable=False,
        doc="DELIVERED | FAILED | BLOCKED | SKIPPED",
    )
    telegram_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    subscriber: Mapped["TelegramSubscriber"] = relationship(back_populates="delivery_logs")
    candidate: Mapped[Optional["HadithCandidate"]] = relationship()
