import pytest
from uuid import uuid4

from app.models.webhook_event import WebhookEvent
from app.services.webhook_processing_service import WebhookProcessingService
from app.models.code_file import CodeFile
from app.models.code_import import CodeImport
from app.services.code_persistence_service import CodePersistenceService
from app.models.user import User
from app.models.workspace import Workspace
from app.models.project import Project
from app.models.repository import Repository
from app.repositories.webhook_event_repository import WebhookEventRepository

def create_webhook_event(db_session, repository, branch):
    event = WebhookEvent(
        repository_id=repository.id,
        delivery_id=f"test-delivery-{branch or 'missing'}",
        event_type="push",
        branch=branch,
        before_commit="before-test",
        after_commit="after-test",
        changed_files={
            "added": [],
            "modified": [],
            "removed": [],
        },
        status="received",
    )

    db_session.add(event)
    db_session.flush()

    return event


def test_non_default_branch_is_skipped(db_session, test_repository):
    event = create_webhook_event(
        db_session,
        test_repository,
        "feature-test",
    )

    service = WebhookProcessingService(db_session)

    result = service.process_event(event)

    assert result["status"] == "skipped"
    assert event.status == "processed"
    assert "Only 'main' is processed." in result["reason"]


def test_missing_branch_marks_event_failed(db_session, test_repository):
    event = create_webhook_event(
        db_session,
        test_repository,
        None,
    )

    service = WebhookProcessingService(db_session)

    result = service.process_event(event)

    assert result["status"] == "failed"
    assert event.status == "failed"
    assert "does not contain a branch" in result["error"]


def test_default_branch_event_is_processed(
    db_session,
    test_repository,
    monkeypatch,
):
    event = create_webhook_event(
        db_session,
        test_repository,
        "main",
    )

    service = WebhookProcessingService(db_session)

    monkeypatch.setattr(
        service,
        "get_github_context",
        lambda repository: (None, "test-user", "test-repository"),
    )

    monkeypatch.setattr(
        service,
        "analyze_changed_files",
        lambda *args: {
            "files_analyzed": 2,
            "files_failed": 0,
            "failures": [],
        },
    )

    monkeypatch.setattr(
        service,
        "delete_removed_files",
        lambda *args: 1,
    )

    result = service.process_event(event)

    assert result["status"] == "processed"
    assert result["files_analyzed"] == 2
    assert result["files_deleted"] == 1
    assert result["files_failed"] == 0
    assert result["documentation_may_be_outdated"] is True
    assert event.status == "processed"


def test_changed_files_filters_non_python_files(
    db_session,
    test_repository,
):
    event = create_webhook_event(
        db_session,
        test_repository,
        "main",
    )

    event.changed_files = {
        "added": ["src/new.py", "README.md"],
        "modified": ["src/main.py", "package.json"],
        "removed": ["src/old.py", "notes.txt"],
    }

    service = WebhookProcessingService(db_session)

    result = service.get_changed_python_files(event)

    assert result == {
        "added": ["src/new.py"],
        "modified": ["src/main.py"],
        "removed": ["src/old.py"],
    }


def test_delete_removed_file_clears_import_references(
    db_session,
    test_repository,
):
    source_file = CodeFile(
        repository_id=test_repository.id,
        path="src/main.py",
        sha="source-sha",
        language="python",
        size=100,
    )

    target_file = CodeFile(
        repository_id=test_repository.id,
        path="src/helper.py",
        sha="target-sha",
        language="python",
        size=80,
    )

    db_session.add_all([source_file, target_file])
    db_session.flush()

    import_record = CodeImport(
        code_file_id=source_file.id,
        resolved_code_file_id=target_file.id,
        module="helper",
        import_kind="import",
        line_number=1,
        imported_names=[],
        relative_level=0,
    )

    db_session.add(import_record)
    db_session.flush()

    source_id = source_file.id
    target_id = target_file.id
    import_id = import_record.id

    persistence = CodePersistenceService(db_session)

    deleted_count = persistence.delete_files(
        test_repository.id,
        ["src/helper.py"],
    )

    assert deleted_count == 1
    assert db_session.get(CodeFile, target_id) is None
    assert db_session.get(CodeFile, source_id) is not None

    remaining_import = db_session.get(CodeImport, import_id)

    assert remaining_import is not None
    assert remaining_import.resolved_code_file_id is None


def test_process_pending_events_returns_correct_summary(
    db_session,
    test_repository,
    test_workspace,
    monkeypatch,
):
    branches = ["main", "feature-one", "feature-two"]

    for branch in branches:
        create_webhook_event(
            db_session,
            test_repository,
            branch,
        )

    service = WebhookProcessingService(db_session)

    outcomes = ["processed", "skipped", "failed"]

    def fake_process_event(event):
        outcome = outcomes.pop(0)
        return {
            "event_id": event.id,
            "status": outcome,
        }

    monkeypatch.setattr(
        service,
        "process_event",
        fake_process_event,
    )

    result = service.process_pending_events(
        owner_id=test_workspace.owner_id,
        limit=10,
    )
    assert result["total"] == 3
    assert result["processed"] == 1
    assert result["skipped"] == 1
    assert result["failed"] == 1
    assert len(result["results"]) == 3


def test_pending_events_are_filtered_by_workspace_owner(
    db_session,
    test_repository,
    test_workspace,
):
    # Create a second user and their repository.
    other_user = User(
        email=f"other-{uuid4().hex}@example.com",
        password_hash="test-password-hash",
    )
    db_session.add(other_user)
    db_session.flush()

    other_workspace = Workspace(
        name="Other Workspace",
        owner_id=other_user.id,
    )
    db_session.add(other_workspace)
    db_session.flush()

    other_project = Project(
        name="Other Project",
        description="Another user's project",
        workspace_id=other_workspace.id,
    )
    db_session.add(other_project)
    db_session.flush()

    other_repository = Repository(
        github_repo_id=uuid4().int % (2**63),
        name="other-repository",
        full_name="other-user/other-repository",
        url="https://github.com/other-user/other-repository",
        default_branch="main",
        project_id=other_project.id,
    )
    db_session.add(other_repository)
    db_session.flush()

    # Create one pending event for each user.
    own_event = create_webhook_event(
        db_session,
        test_repository,
        "main",
    )

    other_event = create_webhook_event(
        db_session,
        other_repository,
        "other-main",
    )

    event_repository = WebhookEventRepository(db_session)

    result = event_repository.get_pending_for_owner(
        owner_id=test_workspace.owner_id,
        limit=20,
    )

    result_ids = [event.id for event in result]

    assert own_event.id in result_ids
    assert other_event.id not in result_ids
