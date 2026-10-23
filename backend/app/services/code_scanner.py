
from pathlib import PurePosixPath


SUPPORTED_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
}

IGNORED_DIRECTORIES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    "coverage",
    ".next",
}

IGNORED_FILENAMES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
}


class CodeScanner:
    """Discover supported source files in a GitHub repository tree."""

    @staticmethod
    def is_supported_file(path: str) -> bool:
        file_path = PurePosixPath(path)

        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return False

        if any(
            part in IGNORED_DIRECTORIES
            for part in file_path.parts
        ):
            return False

        if file_path.name in IGNORED_FILENAMES:
            return False

        return True

    @classmethod
    def scan_tree(cls, tree: list[dict]) -> dict:
        """Filter file entries returned by GitHubService."""

        source_files = []
        directories = []

        for item in tree:
            path = item.get("path", "")

            if not path:
                continue

            if item.get("type") == "tree":
                directories.append(path)
            elif cls.is_supported_file(path):
                source_files.append(path)

        source_files = sorted(set(source_files))
        directories = sorted(set(directories))

        return {
            "source_files": source_files,
            "directories": directories,
            "total_source_files": len(source_files),
        }


    @classmethod
    def retrieve_source_files(
        cls,
        github,
        owner: str,
        repo: str,
        file_paths: list[str],
        ref: str = "main",
    ) -> dict:
        """Retrieve source files while recording individual failures."""

        retrieved = []
        skipped = []
        failed = []

        for path in file_paths:
            try:
                result = github.get_file_content(
                    owner=owner,
                    repo=repo,
                    path=path,
                    ref=ref,
                )
                retrieved.append(result)

            except ValueError as exc:
                message = str(exc)

                if "too large" in message.lower():
                    skipped.append({
                        "path": path,
                        "reason": message,
                    })
                else:
                    failed.append({
                        "path": path,
                        "reason": message,
                    })

        return {
            "files": retrieved,
            "retrieved_count": len(retrieved),
            "skipped": skipped,
            "failed": failed,
        }
