
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    delivery_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    branch: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    before_commit: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    after_commit: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    changed_files: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    commit_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="received",
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    received_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    repository = relationship("Repository")
