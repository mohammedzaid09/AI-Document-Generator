from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.repository import Repository
from app.models.project import Project
from app.models.workspace import Workspace
from app.repositories.github_account_repo import (GitHubAccountRepository,)
from app.services.github_service import GitHubService
from app.services.documentation_context_service import (
    DocumentationContextService,
)

class SourceCodeService:
    def __init__(self, db: Session):
        self.db = db

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

        return account is not None\

    def get_github_service(self, repository_id: int) -> GitHubService:
        owner_id = self.get_repository_owner(repository_id)

        if owner_id is None:
            raise ValueError(
                f"Repository {repository_id} not found."
            )

        if not self.verify_github_connection(owner_id):
            raise ValueError(
                "Connect your GitHub account before retrieving source code."
            )

        return GitHubService(self.db, owner_id)

    def retrieve_repository_sources(
    self,
    repository_id: int,
    max_file_size: int = 500_000,
) -> dict:

        context_service = DocumentationContextService(self.db)

        context = context_service.build_context(repository_id)

        if context is None:
            raise ValueError(
                f"Repository {repository_id} not found."
            )

        repository = context["repository"]

        github = self.get_github_service(repository_id)

        sources = []
        failed_files = []

        for file in context["files"]:

            if file["analysis_status"] != "completed":
                continue

            if file["size"] > max_file_size:
                failed_files.append({
                    "path": file["path"],
                    "error": "File exceeds maximum allowed size.",
                })
                continue

            try:
                result = github.get_file_content(
                    owner=repository["full_name"].split("/")[0],
                    repo=repository["name"],
                    path=file["path"],
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
                    "path": file["path"],
                    "error": str(exc),
                })

        return {
            "repository": repository,
            "total_files": context["total_files"],
            "retrieved_files": len(sources),
            "failed_files": len(failed_files),
            "sources": sources,
            "errors": failed_files,
        }