import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Subscription(Base):
    """Local copy of user-service subscriptions, kept in sync via subscription.events."""

    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    skills: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    location: Mapped[str | None] = mapped_column(String(255))
    min_salary: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str | None] = mapped_column(String(8))
    telegram_chat_id: Mapped[str | None] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Match(Base):
    """One row per (job, subscription) already matched; guarantees no duplicate notifications."""

    __tablename__ = "matches"

    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    subscription_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    matched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Outbox(Base):
    __tablename__ = "outbox"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic: Mapped[str] = mapped_column(String(64))
    key: Mapped[str] = mapped_column(String(128))
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
