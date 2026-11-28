from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.webhook_event import WebhookEvent
from app.models.repository import Repository
from app.models.project import Project
from app.models.workspace import Workspace

class WebhookEventRepository:

    def __init__(self, db: Session):
        self.db = db

    def get_by_delivery_id(
        self,
        delivery_id: str,
    ) -> WebhookEvent | None:

        statement = select(WebhookEvent).where(
            WebhookEvent.delivery_id == delivery_id
        )

        return self.db.scalar(statement)

    def create(
        self,
        repository_id: int,
        delivery_id: str,
        event_type: str,
        branch: str | None = None,
        before_commit: str | None = None,
        after_commit: str | None = None,
        changed_files: dict | None = None,
        commit_message: str | None = None,
    ) -> WebhookEvent:

        event = WebhookEvent(
            repository_id=repository_id,
            delivery_id=delivery_id,
            event_type=event_type,
            branch=branch,
            before_commit=before_commit,
            after_commit=after_commit,
            changed_files=changed_files or {},
            commit_message=commit_message,
            status="received",
        )

        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)

        return event


    def get_by_id(
        self,
        event_id: int,
    ) -> WebhookEvent | None:

        return self.db.get(WebhookEvent, event_id)

    def get_pending(
        self,
        limit: int = 20,
    ) -> list[WebhookEvent]:

        statement = (
            select(WebhookEvent)
            .where(WebhookEvent.status == "received")
            .order_by(WebhookEvent.received_at.asc())
            .limit(limit)
        )

        return list(self.db.scalars(statement).all())

    
    def get_pending_for_owner(
        self,
        owner_id: int,
        limit: int = 20,
    ) -> list[WebhookEvent]:
        """Retrieve pending events belonging to a workspace owner."""

        if limit < 1:
            raise ValueError("Limit must be greater than zero.")

        statement = (
            select(WebhookEvent)
            .join(
                Repository,
                WebhookEvent.repository_id == Repository.id,
            )
            .join(
                Project,
                Repository.project_id == Project.id,
            )
            .join(
                Workspace,
                Project.workspace_id == Workspace.id,
            )
            .where(
                WebhookEvent.status == "received",
                Workspace.owner_id == owner_id,
            )
            .order_by(WebhookEvent.received_at.asc())
            .limit(limit)
        )

        return list(self.db.scalars(statement).all())


    def update_status(
        self,
        event: WebhookEvent,
        status: str,
        error_message: str | None = None,
    ) -> WebhookEvent:

        allowed_statuses = {
            "received",
            "processing",
            "processed",
            "failed",
        }

        if status not in allowed_statuses:
            raise ValueError("Invalid webhook event status.")

        event.status = status
        event.error_message = error_message

        if status in {"processed", "failed"}:
            event.processed_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(event)

        return event