
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.code_file import CodeFile


class CodeSyncService:
    """Identify source files that changed since the last analysis."""

    def __init__(self, db: Session):
        self.db = db

    def find_changed_files(
        self,
        repository_id: int,
        source_files: list[dict],
    ) -> dict:
        stored_files = self.db.scalars(
            select(CodeFile).where(
                CodeFile.repository_id == repository_id
            )
        ).all()

        stored_by_path = {
            item.path: item for item in stored_files
        }

        changed = []
        unchanged = []
        new_files = []

        for item in source_files:
            path = item["path"]
            sha = item.get("sha")
            stored = stored_by_path.get(path)

            if stored is None:
                new_files.append(item)
            elif stored.sha != sha:
                changed.append(item)
            else:
                unchanged.append(item)

        return {
            "new": new_files,
            "changed": changed,
            "unchanged": unchanged,
        }
