
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.routes.documentation import (
    generate_documentation,
    get_repository_documents,
    get_document,
    delete_document,
)


@pytest.fixture
def current_user():
    return SimpleNamespace(id=10)


class FakeDocumentationService:
    def generate_document(self, **kwargs):
        return {"document_id": 1, "status": "completed"}

    def get_generated_documents(self, **kwargs):
        return {
            "repository_id": 2,
            "total_documents": 1,
            "documents": [{"id": 1, "title": "Repository Documentation"}],
        }

    def get_generated_document(self, **kwargs):
        return {"id": 1, "content": "Test documentation"}

    def delete_generated_document(self, **kwargs):
        return {
            "message": "Generated document deleted successfully.",
            "document_id": 1,
        }


@pytest.fixture
def mock_documentation_service(monkeypatch):
    fake_service = FakeDocumentationService()

    monkeypatch.setattr(
        "app.api.routes.documentation.DocumentationGenerationService",
        lambda db: fake_service,
    )

    return fake_service


def test_generate_documentation_route(
    current_user, mock_documentation_service
):
    result = generate_documentation(
        repository_id=2,
        current_user=current_user,
        db=None,
    )

    assert result["document_id"] == 1
    assert result["status"] == "completed"


def test_generate_documentation_handles_value_error(
    current_user, monkeypatch
):
    class FakeService:
        def generate_document(self, **kwargs):
            raise ValueError("Invalid repository")

    monkeypatch.setattr(
        "app.api.routes.documentation.DocumentationGenerationService",
        lambda db: FakeService(),
    )

    with pytest.raises(HTTPException) as exc:
        generate_documentation(2, current_user, None)

    assert exc.value.status_code == 400


def test_generate_documentation_handles_runtime_error(
    current_user, monkeypatch
):
    class FakeService:
        def generate_document(self, **kwargs):
            raise RuntimeError("Gemini generation failed")

    monkeypatch.setattr(
        "app.api.routes.documentation.DocumentationGenerationService",
        lambda db: FakeService(),
    )

    with pytest.raises(HTTPException) as exc:
        generate_documentation(2, current_user, None)

    assert exc.value.status_code == 502


def test_get_repository_documents_route(
    current_user, mock_documentation_service
):
    result = get_repository_documents(
        repository_id=2,
        current_user=current_user,
        db=None,
    )

    assert result["repository_id"] == 2
    assert result["total_documents"] == 1


def test_get_document_route(
    current_user, mock_documentation_service
):
    result = get_document(
        document_id=1,
        current_user=current_user,
        db=None,
    )

    assert result["id"] == 1
    assert result["content"] == "Test documentation"


def test_get_document_handles_missing_document(
    current_user, monkeypatch
):
    class FakeService:
        def get_generated_document(self, **kwargs):
            raise ValueError("Generated document not found.")

    monkeypatch.setattr(
        "app.api.routes.documentation.DocumentationGenerationService",
        lambda db: FakeService(),
    )

    with pytest.raises(HTTPException) as exc:
        get_document(999, current_user, None)

    assert exc.value.status_code == 404


def test_delete_document_route(
    current_user, mock_documentation_service
):
    result = delete_document(
        document_id=1,
        current_user=current_user,
        db=None,
    )

    assert result["document_id"] == 1
    assert "deleted successfully" in result["message"]
