
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.code_file import CodeFile
from app.models.code_entity import CodeEntity
from app.models.code_import import CodeImport


class CodePersistenceService:
    def __init__(self, db: Session):
        self.db = db

    def save_analysis(self, repository_id, analysis_result):
        files_saved = 0
        entities_saved = 0
        imports_saved = 0
        files_failed = 0

        try:
            for item in analysis_result["files"]:
                try:
                    # Save each file independently so one failure
                    # does not roll back other successful files.
                    with self.db.begin_nested():
                        code_file = self.db.scalar(
                            select(CodeFile).where(
                                CodeFile.repository_id == repository_id,
                                CodeFile.path == item["path"],
                            )
                        )

                        if code_file is None:
                            code_file = CodeFile(
                                repository_id=repository_id,
                                path=item["path"],
                                sha=item["sha"],
                                language="python",
                                size=item["size"],
                                analysis_status="pending",
                            )
                            self.db.add(code_file)
                            self.db.flush()

                        code_file.sha = item["sha"]
                        code_file.size = item["size"]
                        code_file.analysis_status = (
                            "completed" if item["success"] else "failed"
                        )
                        code_file.analysis_error = item.get("error")
                        code_file.last_analyzed_at = (
                            datetime.now(timezone.utc).replace(tzinfo=None)
                        )

                        # Replace previously stored analysis results.
                        code_file.entities.clear()
                        code_file.imports.clear()

                        file_entities = 0
                        file_imports = 0

                        if item["success"]:
                            for function in item["functions"]:
                                code_file.entities.append(
                                    CodeEntity(
                                        name=function["name"],
                                        entity_type="function",
                                        start_line=function["line"],
                                        end_line=function.get("end_line"),
                                        details={
                                            "is_async": function["is_async"],
                                            "parameters": function["parameters"],
                                        },
                                    )
                                )
                                file_entities += 1

                            for cls in item["classes"]:
                                code_file.entities.append(
                                    CodeEntity(
                                        name=cls["name"],
                                        entity_type="class",
                                        start_line=cls["line"],
                                        end_line=cls.get("end_line"),
                                        details={"bases": cls["bases"]},
                                    )
                                )
                                file_entities += 1

                            for import_item in item["imports"]:
                                code_file.imports.append(
                                    CodeImport(
                                        module=import_item["module"],
                                        import_kind=import_item["kind"],
                                        line_number=import_item["line"],
                                        imported_names=import_item.get("names", []),
                                        relative_level=import_item.get("level", 0),
                                    )
                                )
                                file_imports += 1

                    # Count only after the file's savepoint succeeds.
                    files_saved += 1
                    entities_saved += file_entities
                    imports_saved += file_imports

                except Exception as exc:
                    files_failed += 1
                    print(
                        f"Failed to save {item.get('path', '<unknown>')}: "
                        f"{type(exc).__name__}: {exc}"
                    )

            self.db.commit()

        except Exception:
            self.db.rollback()
            raise

        return {
            "files_saved": files_saved,
            "entities_saved": entities_saved,
            "imports_saved": imports_saved,
            "files_failed": files_failed,
        }
