

from app.services.code_scanner import CodeScanner
from app.services.code_parser import PythonCodeParser
from app.services.code_sync_service import CodeSyncService


class CodeAnalysisService:
    """Analyze new, changed, or all Python files in a GitHub repository."""

    def __init__(self, github, db):
        self.github = github
        self.db = db

    def analyze_repository(
        self,
        owner: str,
        repo: str,
        repository_id: int,
        branch: str = "main",
        force_reanalysis: bool = False,
    ) -> dict:
        tree_result = self.github.get_repository_tree(
            owner=owner,
            repo=repo,
            branch=branch,
        )

        if tree_result.get("truncated", False):
            raise RuntimeError(
                "GitHub returned a truncated tree. "
                "Refusing to run an incomplete repository sync."
            )

        scan_result = CodeScanner.scan_tree(tree_result["files"])

        python_files = [
            item
            for item in tree_result["files"]
            if item.get("path", "").lower().endswith(".py")
            and CodeScanner.is_supported_file(item.get("path", ""))
        ]

        sync = CodeSyncService(self.db).find_changed_files(
            repository_id=repository_id,
            source_files=python_files,
        )

        if force_reanalysis:
            files_to_fetch = python_files
        else:
            files_to_fetch = sync["new"] + sync["changed"]

        analyzed_files = []
        retrieval_failures = []

        for item in files_to_fetch:
            path = item["path"]

            try:
                file = self.github.get_file_content(
                    owner=owner,
                    repo=repo,
                    path=path,
                    ref=branch,
                )

                parsed = PythonCodeParser.parse(file["content"])

                analyzed_files.append({
                    "path": file["path"],
                    "sha": file["sha"],
                    "size": file["size"],
                    "success": parsed["success"],
                    "error": parsed.get("error"),
                    "functions": parsed["functions"],
                    "classes": parsed["classes"],
                    "imports": parsed["imports"],
                })

            except (ValueError, RuntimeError) as exc:
                retrieval_failures.append({
                    "path": path,
                    "reason": str(exc),
                })

        return {
            "repository": f"{owner}/{repo}",
            "repository_id": repository_id,
            "branch": branch,
            "force_reanalysis": force_reanalysis,
            "tree_truncated": False,
            "total_source_files": scan_result["total_source_files"],
            "python_files_found": len(python_files),
            "new_files": len(sync["new"]),
            "changed_files": len(sync["changed"]),
            "unchanged_files": len(sync["unchanged"]),
            "files_selected_for_analysis": len(files_to_fetch),
            "python_files_retrieved": len(analyzed_files),
            "python_files_parsed": sum(
                1 for item in analyzed_files if item["success"]
            ),
            "python_files_failed": retrieval_failures,
            "files": analyzed_files,
        }
