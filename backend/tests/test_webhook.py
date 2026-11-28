
import asyncio
import hashlib
import hmac
import json

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.routes.webhook import github_webhook


SECRET = "test-webhook-secret"


class FakeRequest:
    def __init__(self, payload):
        self.payload = payload

    async def body(self):
        return self.payload


class FakeRepositoryRepository:
    def __init__(self, db):
        self.repository = SimpleNamespace(
            id=2,
            github_repo_id=123456789,
            full_name="mohammedzaid09/AI-Document-Generator",
        )

    def get_by_github_id(self, github_repo_id):
        if github_repo_id == 123456789:
            return self.repository
        return None


class FakeWebhookEventRepository:
    events = {}

    def __init__(self, db):
        self.db = db

    def get_by_delivery_id(self, delivery_id):
        return self.events.get(delivery_id)

    def create(self, **kwargs):
        event = SimpleNamespace(
            id=len(self.events) + 1,
            status="received",
            **kwargs,
        )
        self.events[event.delivery_id] = event
        return event


@pytest.fixture
def setup_webhook(monkeypatch):
    FakeWebhookEventRepository.events = {}

    monkeypatch.setattr(
        "app.api.routes.webhook.GITHUB_WEBHOOK_SECRET",
        SECRET,
    )

    monkeypatch.setattr(
        "app.api.routes.webhook.RepositoryRepository",
        FakeRepositoryRepository,
    )

    monkeypatch.setattr(
        "app.api.routes.webhook.WebhookEventRepository",
        FakeWebhookEventRepository,
    )


def create_signature(payload):
    digest = hmac.new(
        SECRET.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return f"sha256={digest}"


def create_payload():
    return {
        "repository": {
            "id": 123456789,
        },
        "ref": "refs/heads/main",
        "before": "oldcommit123",
        "after": "newcommit456",
        "head_commit": {
            "id": "newcommit456",
            "message": "Update README",
        },
        "commits": [
            {
                "added": ["new.py"],
                "modified": ["README.md"],
                "removed": ["old.py"],
            }
        ],
    }


def call_webhook(
    payload,
    signature=None,
    event="push",
    delivery_id="delivery-123",
):
    body = json.dumps(payload).encode()

    return asyncio.run(
        github_webhook(
            request=FakeRequest(body),
            x_hub_signature_256=signature,
            x_github_event=event,
            x_github_delivery=delivery_id,
            db=None,
        )
    )


def test_invalid_github_signature(setup_webhook):
    with pytest.raises(HTTPException) as exc:
        call_webhook(
            create_payload(),
            signature="sha256=invalid",
        )

    assert exc.value.status_code == 401


def test_missing_delivery_id(setup_webhook):
    payload = create_payload()
    body = json.dumps(payload).encode()

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            github_webhook(
                request=FakeRequest(body),
                x_hub_signature_256=create_signature(body),
                x_github_event="push",
                x_github_delivery=None,
                db=None,
            )
        )

    assert exc.value.status_code == 400


def test_successful_push_event_persistence(setup_webhook):
    payload = create_payload()
    body = json.dumps(payload).encode()

    result = call_webhook(
        payload,
        signature=create_signature(body),
    )

    assert result["status"] == "received"
    assert result["event_id"] == 1
    assert result["duplicate"] is False
    assert result["repository_id"] == 2
    assert result["branch"] == "main"

    assert result["changed_files"] == {
        "added": ["new.py"],
        "modified": ["README.md"],
        "removed": ["old.py"],
    }


def test_duplicate_delivery_prevention(setup_webhook):
    payload = create_payload()
    body = json.dumps(payload).encode()
    signature = create_signature(body)

    first_result = call_webhook(
        payload,
        signature=signature,
        delivery_id="same-delivery",
    )

    second_result = call_webhook(
        payload,
        signature=signature,
        delivery_id="same-delivery",
    )

    assert first_result["event_id"] == second_result["event_id"]
    assert first_result["duplicate"] is False
    assert second_result["duplicate"] is True


def test_unknown_repository(setup_webhook, monkeypatch):
    class UnknownRepository:
        def __init__(self, db):
            pass

        def get_by_github_id(self, github_repo_id):
            return None

    monkeypatch.setattr(
        "app.api.routes.webhook.RepositoryRepository",
        UnknownRepository,
    )

    payload = create_payload()

    with pytest.raises(HTTPException) as exc:
        call_webhook(
            payload,
            signature=create_signature(
                json.dumps(payload).encode()
            ),
        )

    assert exc.value.status_code == 404
