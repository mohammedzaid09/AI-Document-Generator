from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.repository import Repository
from app.models.code_file import CodeFile
from app.models.code_entity import CodeEntity
from app.models.code_import import CodeImport


class DocumentationContextService:
    def __init__(self, db: Session):
        self.db = db

    def get_repository(self, repository_id: int) -> dict | None:
        repository = self.db.scalar(
            select(Repository).where(
                Repository.id == repository_id
            )
        )

        if repository is None:
            return None

        return {
            "id": repository.id,
            "name": repository.name,
            "full_name": repository.full_name,
            "url": repository.url,
            "default_branch": repository.default_branch,
            "project_id": repository.project_id,
        }

    def get_repository_files(self, repository_id: int) -> list:
        files = self.db.scalars(
            select(CodeFile)
            .where(
                CodeFile.repository_id == repository_id
            )
            .order_by(CodeFile.path)
        ).all()

        return [
            {
                "id": file.id,
                "path": file.path,
                "language": file.language,
                "sha": file.sha,
                "size": file.size,
                "analysis_status": file.analysis_status,
                "analysis_error": file.analysis_error,
            }
            for file in files
        ]

    def get_file_entities(self, file_id: int) -> list:
        entities = self.db.scalars(
            select(CodeEntity)
            .where(CodeEntity.code_file_id == file_id)
            .order_by(CodeEntity.start_line)
        ).all()

        return [
            {
                "name": entity.name,
                "type": entity.entity_type,
                "start_line": entity.start_line,
                "end_line": entity.end_line,
                "details": entity.details,
            }
            for entity in entities
        ]

    def get_file_imports(self, file_id: int) -> list:
        imports = self.db.scalars(
            select(CodeImport)
            .where(CodeImport.code_file_id == file_id)
            .order_by(CodeImport.line_number)
        ).all()

        return [
            {
                "module": item.module,
                "import_kind": item.import_kind,
                "line_number": item.line_number,
                "imported_names": item.imported_names,
                "relative_level": item.relative_level,
                "resolved_file_id": item.resolved_code_file_id,
                "resolved_path": (
                    item.resolved_code_file.path
                    if item.resolved_code_file
                    else None
                ),
            }
            for item in imports
        ]

    def build_context(self, repository_id: int) -> dict | None:
        repository = self.get_repository(repository_id)

        if repository is None:
            return None

        files = self.get_repository_files(repository_id)

        # Calculate analysis status summary.
        analysis_summary = {
            "completed": 0,
            "failed": 0,
            "pending": 0,
        }

        for file in files:
            status = file["analysis_status"]

            if status in analysis_summary:
                analysis_summary[status] += 1

        if not files:
            return {
                "repository": repository,
                "total_files": 0,
                "files": [],
                "analysis_summary": analysis_summary,
                "total_entities": 0,
                "total_imports": 0,
            }

        # Only use successfully analyzed files for structural context.
        completed_files = [
            file for file in files
            if file["analysis_status"] == "completed"
        ]

        file_ids = [file["id"] for file in completed_files]

        entities = []
        imports = []

        if file_ids:
            entities = self.db.scalars(
                select(CodeEntity)
                .where(CodeEntity.code_file_id.in_(file_ids))
                .order_by(CodeEntity.start_line)
            ).all()

            imports = self.db.scalars(
                select(CodeImport)
                .where(CodeImport.code_file_id.in_(file_ids))
                .order_by(CodeImport.line_number)
            ).all()

        # Group entities by file.
        entities_by_file = {}

        for entity in entities:
            entities_by_file.setdefault(
                entity.code_file_id, []
            ).append({
                "name": entity.name,
                "type": entity.entity_type,
                "start_line": entity.start_line,
                "end_line": entity.end_line,
                "details": entity.details,
            })

        # Retrieve resolved internal file paths.
        resolved_file_ids = {
            item.resolved_code_file_id
            for item in imports
            if item.resolved_code_file_id is not None
        }

        resolved_paths = {}

        if resolved_file_ids:
            resolved_files = self.db.scalars(
                select(CodeFile).where(
                    CodeFile.id.in_(resolved_file_ids)
                )
            ).all()

            resolved_paths = {
                file.id: file.path
                for file in resolved_files
            }

        # Group imports by source file.
        imports_by_file = {}

        for item in imports:
            imports_by_file.setdefault(
                item.code_file_id, []
            ).append({
                "module": item.module,
                "import_kind": item.import_kind,
                "line_number": item.line_number,
                "imported_names": item.imported_names,
                "relative_level": item.relative_level,
                "resolved_file_id": item.resolved_code_file_id,
                "resolved_path": resolved_paths.get(
                    item.resolved_code_file_id
                ),
            })

        # Attach structural information to files.
        for file in files:
            file_id = file["id"]

            file["entities"] = entities_by_file.get(
                file_id, []
            )

            file["imports"] = imports_by_file.get(
                file_id, []
            )

        return {
            "repository": repository,
            "total_files": len(files),
            "files": files,
            "analysis_summary": analysis_summary,
            "total_entities": len(entities),
            "total_imports": len(imports),
        }