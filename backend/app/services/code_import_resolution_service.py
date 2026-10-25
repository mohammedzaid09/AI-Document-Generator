from pathlib import PurePosixPath

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.code_file import CodeFile


class CodeImportResolutionService:
    """Resolve Python imports to files in the same repository."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _module_candidates(module: str) -> list[str]:
        """Map a dotted module to possible Python source paths."""
        module = module.strip(".")
        if not module:
            return []

        path = module.replace(".", "/")
        return [f"{path}.py", f"{path}/__init__.py"]

    @staticmethod
    def _relative_module(
        source_path: str,
        module: str,
        relative_level: int,
    ) -> str | None:
        """Resolve a relative import against the source file's package."""
        if relative_level < 1:
            return module or None

        source = PurePosixPath(source_path)
        package_parts = list(source.parent.parts)

        # One dot means the current package; two dots move up one package.
        climb = relative_level - 1
        if climb:
            if climb >= len(package_parts):
                package_parts = []
            else:
                package_parts = package_parts[:-climb]

        module_parts = module.split(".") if module else []
        parts = package_parts + module_parts
        return ".".join(part for part in parts if part) or None

    @staticmethod
    def _source_root_prefix(paths: list[str]) -> str:
        """Strip the backend directory when it is the Python source root."""
        if paths and all(path.startswith("backend/") for path in paths):
            return "backend/"
        return ""

    def resolve_repository(self, repository_id: int) -> dict:
        files = list(
            self.db.scalars(
                select(CodeFile).where(
                    CodeFile.repository_id == repository_id,
                    CodeFile.language == "python",
                )
            ).all()
        )

        prefix = self._source_root_prefix([item.path for item in files])

        def normalize(path: str) -> str:
            if prefix and path.startswith(prefix):
                return path[len(prefix):]
            return path

        path_to_file = {normalize(item.path): item for item in files}
        resolved = 0
        unresolved = 0
        unresolved_details = []

        for source_file in files:
            source_path = normalize(source_file.path)

            for import_item in source_file.imports:
                module = import_item.module or ""
                level = import_item.relative_level or 0

                if level:
                    module = self._relative_module(
                        source_path, module, level
                    ) or ""

                candidates = []

                # For "from package import submodule", try the submodule
                # before falling back to the package itself.
                if import_item.import_kind == "from_import":
                    for name in import_item.imported_names or []:
                        if module:
                            candidates.extend(
                                self._module_candidates(f"{module}.{name}")
                            )
                        else:
                            candidates.extend(self._module_candidates(name))

                candidates.extend(self._module_candidates(module))

                target = next(
                    (
                        path_to_file[candidate]
                        for candidate in candidates
                        if candidate in path_to_file
                    ),
                    None,
                )

                import_item.resolved_code_file_id = (
                    target.id if target is not None else None
                )

                if target is not None:
                    resolved += 1
                else:
                    unresolved += 1
                    unresolved_details.append({
                        "source": source_file.path,
                        "module": import_item.module,
                        "relative_level": level,
                        "line": import_item.line_number,
                    })

        self.db.commit()

        return {
            "repository_id": repository_id,
            "files_checked": len(files),
            "imports_resolved": resolved,
            "imports_unresolved": unresolved,
            "unresolved_details": unresolved_details,
        }
