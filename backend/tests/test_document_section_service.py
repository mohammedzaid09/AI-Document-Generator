import pytest

from app.services.document_section_service import DocumentSectionService


def test_create_and_retrieve_section(db_session, test_generated_document):
    service = DocumentSectionService(db_session)

    section = service.create_section(
        document_id=test_generated_document.id,
        section_key="project_overview",
        title="Project Overview",
        order_index=1,
    )

    assert section.id is not None
    assert section.section_key == "project_overview"
    assert section.status == "pending"

    sections = service.get_sections(test_generated_document.id)

    assert len(sections) == 1
    assert sections[0].title == "Project Overview"


def test_update_and_assemble_document(db_session, test_generated_document):
    service = DocumentSectionService(db_session)

    section = service.create_section(
        document_id=test_generated_document.id,
        section_key="project_overview",
        title="Project Overview",
        order_index=1,
    )

    service.update_section(
        section_id=section.id,
        content="This project generates technical documentation.",
        status="completed",
        model_name="test-model",
        finish_reason="STOP",
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
    )

    content = service.assemble_document(test_generated_document.id)

    assert "## Project Overview" in content
    assert "This project generates technical documentation." in content


def test_assemble_document_rejects_incomplete_sections(
    db_session, test_generated_document
):
    service = DocumentSectionService(db_session)

    service.create_section(
        document_id=test_generated_document.id,
        section_key="project_overview",
        title="Project Overview",
        order_index=1,
    )

    with pytest.raises(ValueError, match="Incomplete sections"):
        service.assemble_document(test_generated_document.id)