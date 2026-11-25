
import pytest
from types import SimpleNamespace

from app.models.generated_document import GeneratedDocument
from app.services.documentation_generation_service import (
    DocumentationGenerationService,
)
from app.services.gemini_provider import GeminiRequestError

@pytest.fixture
def documentation_service(db_session, monkeypatch):
    # Prevent GeminiProvider from requiring or calling an API.
    monkeypatch.setattr(
        "app.services.documentation_generation_service.GeminiProvider",
        lambda: None,
    )

    return DocumentationGenerationService(db_session)


def test_estimate_input_tokens(documentation_service):
    prompt = "a" * 300

    assert documentation_service.estimate_input_tokens(prompt) == 100


def test_reject_empty_prompt(documentation_service):
    with pytest.raises(ValueError, match="Prompt cannot be empty"):
        documentation_service.estimate_input_tokens("")


def test_build_documentation_prompt(documentation_service):
    source_data = {
        "repository": {
            "full_name": "test-user/test-repository",
            "description": "Test repository",
            "default_branch": "main",
        },
        "sources": [
            {
                "path": "app/services/user_service.py",
                "content": "class UserService:\n    pass",
            },
            {
                "path": "app/main.py",
                "content": "app = FastAPI()",
            },
            {
                "path": "README.md",
                "content": "# Test Repository",
            },
        ],
    }

    prompt = documentation_service.build_documentation_prompt(
        source_data
    )

    assert "test-user/test-repository" in prompt
    assert "Project overview and purpose" in prompt
    assert "README.md" in prompt
    assert "FILES INCLUDED: 3" in prompt

    # Verify that important files are prioritized.
    assert prompt.index("FILE: README.md") < prompt.index("FILE: app/main.py")
    assert prompt.index("FILE: app/main.py") < prompt.index(
        "FILE: app/services/user_service.py"
    )


def test_reject_empty_generated_document(documentation_service, test_repository):
    with pytest.raises(
        ValueError,
        match="Generated documentation cannot be empty",
    ):
        documentation_service.save_generated_document(
            repository_id=test_repository.id,
            content=" ",
            model_name="test-model",
        )


def test_save_list_retrieve_and_delete_document(
    documentation_service,
    test_user,
    test_repository,
    db_session,
):
    content = "# Repository Documentation\n\nThis is a test."

    # Save
    document = documentation_service.save_generated_document(
        repository_id=test_repository.id,
        content=content,
        model_name="test-model",
    )

    assert document.id is not None
    assert document.status == "completed"

    # List
    documents = documentation_service.get_generated_documents(
        user_id=test_user.id,
        repository_id=test_repository.id,
    )

    assert documents["total_documents"] == 1
    assert documents["documents"][0]["id"] == document.id

    # Retrieve
    retrieved = documentation_service.get_generated_document(
        user_id=test_user.id,
        document_id=document.id,
    )

    assert retrieved["content"] == content
    assert retrieved["model_name"] == "test-model"

    # Delete
    result = documentation_service.delete_generated_document(
        user_id=test_user.id,
        document_id=document.id,
    )

    assert result["document_id"] == document.id

    remaining = (
        db_session.query(GeneratedDocument)
        .filter(GeneratedDocument.id == document.id)
        .first()
    )

    assert remaining is None


def test_reject_missing_source_code(documentation_service, monkeypatch):
    monkeypatch.setattr(
        documentation_service.source_code_service,
        "retrieve_repository_sources",
        lambda **kwargs: {"sources": []},
    )

    with pytest.raises(
        ValueError,
        match="No source code available",
    ):
        documentation_service.retrieve_source_code(
            repository_id=1,
            user_id=1,
        )


def test_gemini_api_failure_marks_reservation_failed(
    documentation_service,
    monkeypatch,
):
    service = documentation_service

    class FakeGeminiProvider:
        def generate(self, prompt):
            raise GeminiRequestError("Gemini API request failed.")

    failed_reservations = []

    def fake_fail_request(reservation_id):
        failed_reservations.append(reservation_id)

    monkeypatch.setattr(
        service,
        "gemini_provider",
        FakeGeminiProvider(),
    )
    monkeypatch.setattr(
        service.ai_usage_service,
        "fail_request",
        fake_fail_request,
    )

    with pytest.raises(GeminiRequestError):
        service.generate_with_gemini(
            prompt="Test prompt",
            reservation_id=101,
        )

    assert failed_reservations == [101]


def test_post_response_validation_failure_preserves_reservation(
    documentation_service,
    monkeypatch,
):
    service = documentation_service

    class FakeGeminiProvider:
        def generate(self, prompt):
            raise RuntimeError("Invalid token usage metadata.")

    failed_reservations = []

    def fake_fail_request(reservation_id):
        failed_reservations.append(reservation_id)

    monkeypatch.setattr(
        service,
        "gemini_provider",
        FakeGeminiProvider(),
    )
    monkeypatch.setattr(
        service.ai_usage_service,
        "fail_request",
        fake_fail_request,
    )

    with pytest.raises(
        RuntimeError,
        match="reservation must be checked",
    ):
        service.generate_with_gemini(
            prompt="Test prompt",
            reservation_id=102,
        )

    assert failed_reservations == []


def test_save_incomplete_generated_document(
    documentation_service,
    test_repository,
):
    content = "# Project Overview\n\nPartial documentation."

    document = documentation_service.save_generated_document(
        repository_id=test_repository.id,
        content=content,
        model_name="gemini-3.8-flash",
        status="incomplete",
    )

    assert document.id is not None
    assert document.status == "incomplete"
    assert document.content == content
    assert document.model_name == "gemini-3.8-flash"


def test_generate_document_creates_four_sections(
    documentation_service,
    test_user,
    test_repository,
):
    service = documentation_service

    source_data = {
        "repository": {
            "full_name": "test-user/test-repository",
            "description": "Test repository",
            "default_branch": "main",
        },
        "sources": [
            {
                "path": "README.md",
                "content": "# Test project",
            },
            {
                "path": "app/main.py",
                "content": "app = FastAPI()",
            },
            {
                "path": "app/services/user_service.py",
                "content": "class UserService: pass",
            },
        ],
    }

    reservations = []
    generated_sections = []

    service.repository_service.get_repository = lambda **kwargs: test_repository

    service.retrieve_source_code = lambda **kwargs: source_data

    def fake_reserve_request(**kwargs):
        reservation_id = len(reservations) + 1
        reservations.append(kwargs)
        return SimpleNamespace(id=reservation_id)

    def fake_generate_with_gemini(prompt, reservation_id):
        generated_sections.append(reservation_id)
        return {
            "content": f"Generated section {reservation_id}.",
            "model": "test-model",
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
            "finish_reason": "STOP",
            "is_complete": True,
        }

    service.ai_usage_service.reserve_request = fake_reserve_request
    service.generate_with_gemini = fake_generate_with_gemini

    result = service.generate_document(
        user_id=test_user.id,
        repository_id=test_repository.id,
    )

    assert result["status"] == "completed"
    assert len(result["sections"]) == 4
    assert len(reservations) == 4
    assert generated_sections == [1, 2, 3, 4]

    assert all(
        section["status"] == "completed"
        for section in result["sections"]
    )

    document = service.get_generated_document(
        user_id=test_user.id,
        document_id=result["document_id"],
    )

    assert "Project Overview" in document["content"]
    assert "Codebase Architecture" in document["content"]
    assert "Technical Design" in document["content"]
    assert "Setup and Testing" in document["content"]


def test_incomplete_section_stops_generation(
    documentation_service,
    test_user,
    test_repository,
):
    service = documentation_service

    source_data = {
        "repository": {
            "full_name": "test-user/test-repository",
            "description": "Test repository",
            "default_branch": "main",
        },
        "sources": [
            {
                "path": "README.md",
                "content": "# Test project",
            },
        ],
    }

    reservations = []
    generated_sections = []

    service.repository_service.get_repository = lambda **kwargs: test_repository
    service.retrieve_source_code = lambda **kwargs: source_data

    def fake_reserve_request(**kwargs):
        reservation_id = len(reservations) + 1
        reservations.append(kwargs)
        return SimpleNamespace(id=reservation_id)

    def fake_generate_with_gemini(prompt, reservation_id):
        generated_sections.append(reservation_id)

        return {
            "content": "Partial documentation.",
            "model": "test-model",
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
            "finish_reason": "MAX_TOKENS",
            "is_complete": False,
        }

    service.ai_usage_service.reserve_request = fake_reserve_request
    service.generate_with_gemini = fake_generate_with_gemini

    result = service.generate_document(
        user_id=test_user.id,
        repository_id=test_repository.id,
    )

    assert result["status"] == "incomplete"
    assert len(reservations) == 1
    assert generated_sections == [1]

    assert result["sections"][0]["status"] == "incomplete"
    assert all(
        section["status"] == "pending"
        for section in result["sections"][1:]
    )

def test_build_section_prompt_includes_output_constraints(
    documentation_service,
):
    source_data = {
        "repository": {
            "full_name": "test-user/test-repository",
            "description": "Test repository",
            "default_branch": "main",
        },
        "sources": [
            {
                "path": "README.md",
                "content": "# Test project",
            },
            {
                "path": "app/main.py",
                "content": "app = FastAPI()",
            },
        ],
    }

    prompt = documentation_service.build_section_prompt(
        source_data=source_data,
        section_key="overview",
        title="Project Overview",
    )

    assert "Target approximately 600 output tokens" in prompt
    assert "Never exceed the configured output-token limit" in prompt
    assert "Use only the supplied source code" in prompt