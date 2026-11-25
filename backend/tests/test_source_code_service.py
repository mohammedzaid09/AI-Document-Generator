
import pytest

from app.services.source_code_service import SourceCodeService


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        ".env.example",
        "config/.env.production",
        ".git/config",
        ".ssh/id_rsa",
        ".aws/credentials",
        "venv/lib/package.py",
        "node_modules/package/index.js",
        "certificates/server.pem",
        "config/terraform.tfstate",
        "secrets.json",
    ],
)
def test_sensitive_files_are_rejected(path):
    assert SourceCodeService.is_sensitive_file(path) is True


@pytest.mark.parametrize(
    "path",
    [
        "app/main.py",
        "app/services/user_service.py",
        "README.md",
        "requirements.txt",
        "tests/test_app.py",
    ],
)
def test_normal_source_files_are_allowed(path):
    assert SourceCodeService.is_sensitive_file(path) is False


def test_repository_owner(
    db_session, test_user, test_repository
):
    service = SourceCodeService(db_session)

    owner_id = service.get_repository_owner(test_repository.id)

    assert owner_id == test_user.id


def test_reject_repository_access_by_non_owner(
    db_session, test_user, test_repository, monkeypatch
):
    service = SourceCodeService(db_session)

    monkeypatch.setattr(
        service,
        "verify_github_connection",
        lambda user_id: True,
    )

    with pytest.raises(ValueError, match="do not have permission"):
        service.get_github_service(
            repository_id=test_repository.id,
            user_id=test_user.id + 100,
        )


def test_reject_missing_github_connection(
    db_session, test_user, test_repository, monkeypatch
):
    service = SourceCodeService(db_session)

    monkeypatch.setattr(
        service,
        "verify_github_connection",
        lambda user_id: False,
    )

    with pytest.raises(ValueError, match="Connect your GitHub account"):
        service.get_github_service(
            repository_id=test_repository.id,
            user_id=test_user.id,
        )


def test_retrieve_repository_sources(
    db_session, test_user, test_repository, monkeypatch
):
    service = SourceCodeService(db_session)

    fake_context = {
        "repository": {
            "full_name": "test-user/test-repository",
            "name": "test-repository",
            "default_branch": "main",
        },
        "total_files": 3,
        "files": [
            {
                "id": 1,
                "path": "app/main.py",
                "size": 100,
                "analysis_status": "completed",
                "entities": [],
                "imports": [],
            },
            {
                "id": 2,
                "path": ".env",
                "size": 50,
                "analysis_status": "completed",
                "entities": [],
                "imports": [],
            },
            {
                "id": 3,
                "path": "large.py",
                "size": 1000,
                "analysis_status": "completed",
                "entities": [],
                "imports": [],
            },
        ],
    }

    class FakeContextService:
        def __init__(self, db):
            pass

        def build_context(self, repository_id):
            return fake_context

    class FakeGitHubService:
        def get_file_content(self, **kwargs):
            return {
                "path": kwargs["path"],
                "sha": "test-sha",
                "size": 100,
                "content": "print('Hello')",
            }

    monkeypatch.setattr(
        "app.services.source_code_service.DocumentationContextService",
        FakeContextService,
    )

    monkeypatch.setattr(
        service,
        "get_github_service",
        lambda **kwargs: FakeGitHubService(),
    )

    result = service.retrieve_repository_sources(
        repository_id=test_repository.id,
        user_id=test_user.id,
        max_file_size=500,
    )

    assert result["total_files"] == 3
    assert result["retrieved_files"] == 1
    assert result["skipped_files"] == 1
    assert result["failed_files"] == 1
    assert result["sources"][0]["path"] == "app/main.py"
    assert result["errors"][0]["path"] == "large.py"
