
import json
import hashlib
import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import GITHUB_WEBHOOK_SECRET
from app.core.database import get_db
from app.repositories.repo_repository import RepositoryRepository
from app.repositories.webhook_event_repository import WebhookEventRepository
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.webhook_processing_service import WebhookProcessingService

router = APIRouter(
    prefix="/api/webhooks",
    tags=["Webhooks"],
)


def verify_github_signature(
    payload: bytes,
    signature: str | None,
) -> bool:
    if not GITHUB_WEBHOOK_SECRET or not signature:
        return False

    expected_signature = "sha256=" + hmac.new(
        GITHUB_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected_signature, signature)


@router.post("/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None),
    x_github_event: str | None = Header(default=None),
    x_github_delivery: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    payload = await request.body()

    if not verify_github_signature(payload, x_hub_signature_256):
        raise HTTPException(
            status_code=401,
            detail="Invalid GitHub webhook signature",
        )

    if x_github_event == "ping":
        return {"status": "received", "event": "ping"}

    if x_github_event != "push":
        return {
            "status": "ignored",
            "event": x_github_event or "unknown",
        }

    if not x_github_delivery:
        raise HTTPException(
            status_code=400,
            detail="GitHub delivery ID is missing",
        )

    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(
            status_code=400,
            detail="Invalid JSON payload",
        ) from None

    event_repository = WebhookEventRepository(db)

    # Prevent duplicate delivery processing.
    existing_event = event_repository.get_by_delivery_id(
        x_github_delivery
    )

    if existing_event:
        return {
            "status": existing_event.status,
            "event_id": existing_event.id,
            "duplicate": True,
        }

    github_data = data.get("repository") or {}
    head_commit = data.get("head_commit") or {}

    github_repo_id = github_data.get("id")

    if github_repo_id is None:
        raise HTTPException(
            status_code=400,
            detail="Repository ID missing from GitHub payload",
        )

    repository_repository = RepositoryRepository(db)

    stored_repository = repository_repository.get_by_github_id(
        github_repo_id
    )

    if not stored_repository:
        raise HTTPException(
            status_code=404,
            detail="GitHub repository is not connected to a project",
        )

    commits = data.get("commits") or []

    added = set()
    modified = set()
    removed = set()

    for commit in commits:
        added.update(commit.get("added") or [])
        modified.update(commit.get("modified") or [])
        removed.update(commit.get("removed") or [])

    added -= modified | removed
    modified -= removed

    changed_files = {
        "added": sorted(added),
        "modified": sorted(modified),
        "removed": sorted(removed),
    }

    branch = data.get("ref", "").removeprefix("refs/heads/")

    try:
        event = event_repository.create(
            repository_id=stored_repository.id,
            delivery_id=x_github_delivery,
            event_type="push",
            branch=branch,
            before_commit=data.get("before"),
            after_commit=data.get("after"),
            changed_files=changed_files,
            commit_message=head_commit.get("message"),
        )
    except IntegrityError:
        # Another request may have saved the same delivery concurrently.
        db.rollback()

        existing_event = event_repository.get_by_delivery_id(
            x_github_delivery
        )

        if existing_event:
            return {
                "status": existing_event.status,
                "event_id": existing_event.id,
                "duplicate": True,
            }

        raise

    return {
        "status": event.status,
        "event_id": event.id,
        "duplicate": False,
        "repository": stored_repository.full_name,
        "repository_id": stored_repository.id,
        "branch": event.branch,
        "before": event.before_commit,
        "after": event.after_commit,
        "changed_files": event.changed_files,
    }


@router.post("/process-pending")
def process_pending_webhooks(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Process pending webhook events belonging to the authenticated user."""

    service = WebhookProcessingService(db)

    return service.process_pending_events(
        owner_id=current_user.id,
        limit=limit,
    )
