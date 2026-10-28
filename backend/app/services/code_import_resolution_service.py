
import re
import sys
from importlib.metadata import packages_distributions
from pathlib import Path, PurePosixPath

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.code_file import CodeFile


class CodeImportResolutionService:
    """Resolve and classify Python imports."""

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

        package_parts = list(PurePosixPath(source_path).parent.parts)
        climb = relative_level - 1

        if climb:
            package_parts = (
                package_parts[:-climb]
                if climb < len(package_parts)
                else []
            )

        module_parts = module.split(".") if module else []
        parts = package_parts + module_parts
        return ".".join(part for part in parts if part) or None

    @staticmethod
    def _source_root_prefix(paths: list[str]) -> str:
        """Strip the backend directory when it is the Python source root."""
        if paths and all(path.startswith("backend/") for path in paths):
            return "backend/"
        return ""

    @staticmethod
    def _normalize_distribution(name: str) -> str:
        """Normalize package names for comparisons."""
        return re.sub(r"[-_.]+", "-", name).lower()

    @classmethod
    def _load_declared_distributions(cls) -> set[str]:
        """Read declared dependencies from requirements.txt."""
        requirements_path = (
            Path(__file__).resolve().parents[2] / "requirements.txt"
        )
        declared = set()

        if not requirements_path.exists():
            return declared

        try:
            requirements_text = requirements_path.read_text(
                encoding="utf-16"
            )
        except UnicodeError:
            requirements_text = requirements_path.read_text(
                encoding="utf-8-sig",
                errors="replace",
            )

        for line in requirements_text.splitlines():
            line = line.strip()

            if not line or line.startswith("#") or line.startswith(("-", ".")):
                continue

            match = re.match(r"([A-Za-z0-9_.-]+)", line)
            if match:
                declared.add(
                    cls._normalize_distribution(match.group(1))
                )

        return declared

    @classmethod
    def _classify_import(
        cls,
        module: str,
        relative_level: int,
        target: CodeFile | None,
        module_distributions: dict[str, list[str]],
        declared_distributions: set[str],
    ) -> str:
        """Classify an import without guessing that every unknown is external."""
        if target is not None:
            return "internal"

        if relative_level > 0 or not module:
            return "unknown"

        root_module = module.split(".", 1)[0]

        if root_module in sys.stdlib_module_names:
            return "stdlib"

        # Directly match import names to declared dependency names.
        if (
            cls._normalize_distribution(root_module)
            in declared_distributions
        ):
            return "third_party"

        distributions = module_distributions.get(root_module, [])
        for distribution in distributions:
            if (
                cls._normalize_distribution(distribution)
                in declared_distributions
            ):
                return "third_party"

        # Handle common import names that differ from distribution names.
        aliases = {
            "dotenv": "python-dotenv",
            "jwt": "pyjwt",
            "yaml": "pyyaml",
            "PIL": "pillow",
            "cv2": "opencv-python",
            "dateutil": "python-dateutil",
        }

        alias = aliases.get(root_module)
        if alias and cls._normalize_distribution(alias) in declared_distributions:
            return "third_party"

        return "unknown"

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
        module_distributions = packages_distributions()
        declared_distributions = self._load_declared_distributions()

        counts = {
            "internal": 0,
            "stdlib": 0,
            "third_party": 0,
            "unknown": 0,
        }
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

                if import_item.import_kind == "from_import":
                    for name in import_item.imported_names or []:
                        candidate_module = (
                            f"{module}.{name}" if module else name
                        )
                        candidates.extend(
                            self._module_candidates(candidate_module)
                        )

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

                category = self._classify_import(
                    module=import_item.module or "",
                    relative_level=level,
                    target=target,
                    module_distributions=module_distributions,
                    declared_distributions=declared_distributions,
                )
                counts[category] += 1

                if target is None:
                    unresolved_details.append({
                        "source": source_file.path,
                        "module": import_item.module,
                        "relative_level": level,
                        "line": import_item.line_number,
                        "classification": category,
                    })

        self.db.commit()

        return {
            "repository_id": repository_id,
            "files_checked": len(files),
            "imports_resolved": counts["internal"],
            "imports_unresolved": (
                counts["stdlib"]
                + counts["third_party"]
                + counts["unknown"]
            ),
            "classification_counts": counts,
            "unresolved_details": unresolved_details,
        }
