
import base64
from types import SimpleNamespace

import pytest

from app.services.github_service import GitHubService


@pytest.fixture
def github_service(monkeypatch):
    fake_account = SimpleNamespace(
        access_token_encrypted="fake-encrypted-token"
    )

    class FakeAccountRepository:
        def __init__(self, db):
            pass

        def get_by_user_id(self, user_id):
            return fake_account

    monkeypatch.setattr(
        "app.services.github_service.GitHubAccountRepository",
        FakeAccountRepository,
    )

    monkeypatch.setattr(
        "app.services.github_service.decrypt_github_token",
        lambda token: "fake-access-token",
    )

    return GitHubService(db=None, user_id=1)


def test_github_service_initializes_authorization(github_service):
    assert github_service.headers["Authorization"] == (
        "Bearer fake-access-token"
    )


def test_reject_missing_github_account(monkeypatch):
    class FakeAccountRepository:
        def __init__(self, db):
            pass

        def get_by_user_id(self, user_id):
            return None

    monkeypatch.setattr(
        "app.services.github_service.GitHubAccountRepository",
        FakeAccountRepository,
    )

    with pytest.raises(ValueError, match="Connect your GitHub account"):
        GitHubService(db=None, user_id=1)


def test_get_repository(github_service, monkeypatch):
    def fake_get(url, **kwargs):
        return SimpleNamespace(
            status_code=200,
            json=lambda: {"full_name": "test-user/test-repository"},
        )

    monkeypatch.setattr(
        "app.services.github_service.httpx.get",
        fake_get,
    )

    result = github_service.get_repository(
        "test-user",
        "test-repository",
    )

    assert result["full_name"] == "test-user/test-repository"


def test_get_repository_handles_api_error(github_service, monkeypatch):
    def fake_get(url, **kwargs):
        return SimpleNamespace(
            status_code=404,
            text="Not Found",
        )

    monkeypatch.setattr(
        "app.services.github_service.httpx.get",
        fake_get,
    )

    with pytest.raises(ValueError, match="GitHub API error: 404"):
        github_service.get_repository(
            "test-user",
            "missing-repository",
        )


def test_get_file_content_success(github_service, monkeypatch):
    encoded_content = base64.b64encode(
        b"print('Hello World')"
    ).decode("utf-8")

    def fake_get(url, **kwargs):
        assert "app/main.py" in url

        return SimpleNamespace(
            status_code=200,
            json=lambda: {
                "type": "file",
                "size": 20,
                "encoding": "base64",
                "content": encoded_content,
                "sha": "test-sha",
            },
        )

    monkeypatch.setattr(
        "app.services.github_service.httpx.get",
        fake_get,
    )

    result = github_service.get_file_content(
        owner="test-user",
        repo="test-repository",
        path="app/main.py",
    )

    assert result["content"] == "print('Hello World')"
    assert result["sha"] == "test-sha"


def test_get_file_content_rejects_large_file(
    github_service, monkeypatch
):
    monkeypatch.setattr(
        "app.services.github_service.httpx.get",
        lambda *args, **kwargs: SimpleNamespace(
            status_code=200,
            json=lambda: {
                "type": "file",
                "size": 1000,
                "encoding": "base64",
                "content": "",
            },
        ),
    )

    with pytest.raises(ValueError, match="too large"):
        github_service.get_file_content(
            "test-user",
            "test-repository",
            "large.py",
            max_size=500,
        )


def test_get_file_content_rejects_invalid_encoding(
    github_service, monkeypatch
):
    monkeypatch.setattr(
        "app.services.github_service.httpx.get",
        lambda *args, **kwargs: SimpleNamespace(
            status_code=200,
            json=lambda: {
                "type": "file",
                "size": 10,
                "encoding": "utf-8",
                "content": "print('Hello')",
            },
        ),
    )

    with pytest.raises(ValueError, match="Unsupported or missing"):
        github_service.get_file_content(
            "test-user",
            "test-repository",
            "main.py",
        )


def test_get_file_content_rejects_invalid_base64(
    github_service, monkeypatch
):
    monkeypatch.setattr(
        "app.services.github_service.httpx.get",
        lambda *args, **kwargs: SimpleNamespace(
            status_code=200,
            json=lambda: {
                "type": "file",
                "size": 10,
                "encoding": "base64",
                "content": "invalid-base64!!!",
            },
        ),
    )

    with pytest.raises(ValueError, match="Unable to decode"):
        github_service.get_file_content(
            "test-user",
            "test-repository",
            "main.py",
        )


def test_get_file_content_accepts_empty_file(
    github_service, monkeypatch
):
    monkeypatch.setattr(
        "app.services.github_service.httpx.get",
        lambda *args, **kwargs: SimpleNamespace(
            status_code=200,
            json=lambda: {
                "type": "file",
                "size": 0,
                "encoding": "base64",
                "content": "",
                "sha": "empty-sha",
            },
        ),
    )

    result = github_service.get_file_content(
        "test-user",
        "test-repository",
        "empty.py",
    )

    assert result["content"] == ""
    assert result["sha"] == "empty-sha"
