
from sqlalchemy.orm import Session

from app.models.document_section import DocumentSection
from app.models.generated_document import GeneratedDocument


class DocumentSectionService:
    def __init__(self, db: Session):
        self.db = db

    def create_section(
        self,
        document_id: int,
        section_key: str,
        title: str,
        order_index: int,
    ) -> DocumentSection:

        document = (
            self.db.query(GeneratedDocument)
            .filter(GeneratedDocument.id == document_id)
            .first()
        )

        if document is None:
            raise ValueError("Generated document not found.")

        existing_section = (
            self.db.query(DocumentSection)
            .filter(
                DocumentSection.document_id == document_id,
                DocumentSection.section_key == section_key,
            )
            .first()
        )

        if existing_section:
            return existing_section

        section = DocumentSection(
            document_id=document_id,
            section_key=section_key,
            title=title,
            content="",
            status="pending",
            order_index=order_index,
        )

        try:
            self.db.add(section)
            self.db.commit()
            self.db.refresh(section)

            return section

        except Exception:
            self.db.rollback()
            raise

    def update_section(
        self,
        section_id: int,
        content: str,
        status: str,
        model_name: str | None = None,
        finish_reason: str | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int = 0,
    ) -> DocumentSection:

        section = (
            self.db.query(DocumentSection)
            .filter(DocumentSection.id == section_id)
            .first()
        )

        if section is None:
            raise ValueError("Document section not found.")

        if status not in {"pending", "generating", "completed", "incomplete", "failed"}:
            raise ValueError("Invalid document section status.")

        if min(input_tokens, output_tokens, total_tokens) < 0:
            raise ValueError("Token counts cannot be negative.")

        if total_tokens != input_tokens + output_tokens:
            raise ValueError("Total tokens must equal input plus output tokens.")

        section.content = content
        section.status = status
        section.model_name = model_name
        section.finish_reason = finish_reason
        section.input_tokens = input_tokens
        section.output_tokens = output_tokens
        section.total_tokens = total_tokens

        try:
            self.db.commit()
            self.db.refresh(section)

            return section

        except Exception:
            self.db.rollback()
            raise

    def get_sections(self, document_id: int) -> list[DocumentSection]:

        return (
            self.db.query(DocumentSection)
            .filter(DocumentSection.document_id == document_id)
            .order_by(DocumentSection.order_index.asc())
            .all()
        )

    def assemble_document(self, document_id: int) -> str:

        sections = self.get_sections(document_id)

        if not sections:
            raise ValueError("No document sections found.")

        incomplete_sections = [
            section.title
            for section in sections
            if section.status != "completed"
        ]

        if incomplete_sections:
            raise ValueError(
                "Cannot assemble document. Incomplete sections: "
                + ", ".join(incomplete_sections)
            )

        content_parts = []

        for section in sections:
            content_parts.append(
                f"## {section.title}\n\n{section.content.strip()}"
            )

        return "\n\n".join(content_parts)

    def synchronize_document(self, document_id: int) -> GeneratedDocument:
        document = (
            self.db.query(GeneratedDocument)
            .filter(GeneratedDocument.id == document_id)
            .first()
        )

        if document is None:
            raise ValueError("Generated document not found.")

        sections = self.get_sections(document_id)

        if not sections:
            raise ValueError("No document sections found.")

        if all(section.status == "completed" for section in sections):
            document.content = self.assemble_document(document_id)
            document.status = "completed"

        elif any(section.status == "failed" for section in sections):
            document.status = "failed"

        elif any(section.status == "incomplete" for section in sections):
            document.status = "incomplete"

        else:
            document.status = "generating"

        try:
            self.db.commit()
            self.db.refresh(document)
            return document

        except Exception:
            self.db.rollback()
            raise
