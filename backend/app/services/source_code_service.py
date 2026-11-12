
from pathlib import PurePosixPath

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.repository import Repository
from app.models.project import Project
from app.models.workspace import Workspace
from app.repositories.github_account_repo import GitHubAccountRepository
from app.services.github_service import GitHubService
from app.services.documentation_context_service import (
    DocumentationContextService,
)


class SourceCodeService:

    SENSITIVE_DIRECTORIES = {
        ".git",
        ".ssh",
        ".aws",
        ".azure",
        ".kube",
        ".gnupg",
        "node_modules",
        "venv",
        ".venv",
        "__pycache__",
    }

    SENSITIVE_FILENAMES = {
        ".npmrc",
        ".pypirc",
        ".netrc",
        "credentials",
        "credentials.json",
        "secrets.json",
        "service-account.json",
        "id_rsa",
        "id_ed25519",
    }

    SENSITIVE_SUFFIXES = (
        ".pem",
        ".key",
        ".p12",
        ".pfx",
        ".p8",
        ".jks",
        ".keystore",
        ".tfstate",
        ".tfvars",
    )

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def is_sensitive_file(path: str) -> bool:
        normalized_path = path.replace("\\", "/")
        parts = PurePosixPath(normalized_path).parts

        if not parts:
            return True

        lowered_parts = [part.lower() for part in parts]
        filename = lowered_parts[-1]

        # Exclude sensitive directories.
        if any(
            part in SourceCodeService.SENSITIVE_DIRECTORIES
            for part in lowered_parts
        ):
            return True

        # Exclude environment files, including example variants.
        if filename == ".env" or filename.startswith(".env."):
            return True

        # Exclude known credential and private-key filenames.
        if filename in SourceCodeService.SENSITIVE_FILENAMES:
            return True

        # Exclude sensitive file extensions.
        if filename.endswith(SourceCodeService.SENSITIVE_SUFFIXES):
            return True

        return False

    def get_repository_owner(self, repository_id: int) -> int | None:
        statement = (
            select(Workspace.owner_id)
            .join(Project, Project.workspace_id == Workspace.id)
            .join(Repository, Repository.project_id == Project.id)
            .where(Repository.id == repository_id)
        )

        return self.db.scalar(statement)

    def verify_github_connection(self, user_id: int) -> bool:
        account_repository = GitHubAccountRepository(self.db)

        account = account_repository.get_by_user_id(user_id)

        return account is not None

    def get_github_service(
        self,
        repository_id: int,
        user_id: int,
    ) -> GitHubService:

        owner_id = self.get_repository_owner(repository_id)

        if owner_id is None:
            raise ValueError(
                f"Repository {repository_id} not found."
            )

        # Verify that the requesting user owns the repository.
        if owner_id != user_id:
            raise ValueError(
                "You do not have permission to access this repository."
            )

        # Verify the requesting user's GitHub connection.
        if not self.verify_github_connection(user_id):
            raise ValueError(
                "Connect your GitHub account before retrieving source code."
            )

        return GitHubService(self.db, user_id)

    def retrieve_repository_sources(
        self,
        repository_id: int,
        user_id: int,
        max_file_size: int = 500_000,
    ) -> dict:

        context_service = DocumentationContextService(self.db)

        context = context_service.build_context(repository_id)

        if context is None:
            raise ValueError(
                f"Repository {repository_id} not found."
            )

        repository = context["repository"]

        github = self.get_github_service(
            repository_id=repository_id,
            user_id=user_id,
        )

        sources = []
        failed_files = []
        skipped_files = []

        for file in context["files"]:

            if file["analysis_status"] != "completed":
                continue

            file_path = file["path"]

            # Skip sensitive files before retrieving their contents.
            if self.is_sensitive_file(file_path):
                skipped_files.append(file_path)
                continue

            if file["size"] > max_file_size:
                failed_files.append({
                    "path": file_path,
                    "error": "File exceeds maximum allowed size.",
                })
                continue

            try:
                result = github.get_file_content(
                    owner=repository["full_name"].split("/", 1)[0],
                    repo=repository["name"],
                    path=file_path,
                    ref=repository["default_branch"],
                    max_size=max_file_size,
                )

                sources.append({
                    "file_id": file["id"],
                    "path": result["path"],
                    "sha": result["sha"],
                    "size": result["size"],
                    "content": result["content"],
                    "entities": file["entities"],
                    "imports": file["imports"],
                })

            except Exception as exc:
                failed_files.append({
                    "path": file_path,
                    "error": str(exc),
                })

        return {
            "repository": repository,
            "total_files": context["total_files"],
            "retrieved_files": len(sources),
            "failed_files": len(failed_files),
            "skipped_files": len(skipped_files),
            "sources": sources,
            "errors": failed_files,
        }
