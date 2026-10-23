import json
import hashlib
import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import GITHUB_WEBHOOK_SECRET
from app.core.database import get_db
from app.repositories.repo_repository import RepositoryRepository

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

    try:
        data = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(
            status_code=400,
            detail="Invalid JSON payload",
        ) from None

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

    result = {
        "event": "push",
        "repository": stored_repository.full_name,
        "repository_id": stored_repository.id,
        "github_repo_id": stored_repository.github_repo_id,
        "project_id": stored_repository.project_id,
        "branch": data.get("ref", "").removeprefix("refs/heads/"),
        "before": data.get("before"),
        "after": data.get("after"),
        "commit": head_commit.get("id"),
        "message": head_commit.get("message"),
        "changed_files": {
            "added": sorted(added),
            "modified": sorted(modified),
            "removed": sorted(removed),
        },
    }

    print("Processed GitHub push event:")
    print(result)

    return result
