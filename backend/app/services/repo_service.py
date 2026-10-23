from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.project_repository import ProjectRepository
from app.repositories.repo_repository import RepositoryRepository
from app.repositories.workspace_repository import WorkspaceRepository
from app.services.github_service import GitHubService

class RepositoryService:

    def __init__(self, db: Session):
        self.db = db
        self.repository_repository = RepositoryRepository(db)
        self.project_repository = ProjectRepository(db)
        self.workspace_repository = WorkspaceRepository(db)

    def _verify_project_access(
        self,
        project_id: int,
        owner_id: int,
    ):

        project = self.project_repository.get_by_id(project_id)

        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found",
            )

        workspace = self.workspace_repository.get_by_id(
            project.workspace_id
        )

        if not workspace or workspace.owner_id != owner_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this project",
            )

        return project

    def create_repository(
        self,
        project_id: int,
        owner_id: int,
        github_owner: str,
        github_repo: str,
    ):

        self._verify_project_access(
            project_id=project_id,
            owner_id=owner_id,
        )

        try:
            github_service = GitHubService(
                db=self.db,
                user_id=owner_id,
            )

            github_data = github_service.get_repository(
                owner=github_owner,
                repo=github_repo,
            )

        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error),
            )

        github_repo_id = github_data["id"]

        existing_repository = (
            self.repository_repository.get_by_github_id(
                github_repo_id
            )
        )

        if existing_repository:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="GitHub repository is already connected",
            )

        return self.repository_repository.create(
            github_repo_id=github_data["id"],
            name=github_data["name"],
            full_name=github_data["full_name"],
            url=github_data["html_url"],
            default_branch=github_data["default_branch"],
            project_id=project_id,
        )

    def get_project_repositories(
        self,
        project_id: int,
        owner_id: int,
    ):

        self._verify_project_access(
            project_id=project_id,
            owner_id=owner_id,
        )

        return self.repository_repository.get_by_project(
            project_id
        )

    def get_repository(
        self,
        repository_id: int,
        owner_id: int,
    ):

        repository = self.repository_repository.get_by_id(
            repository_id
        )

        if not repository:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repository not found",
            )

        self._verify_project_access(
            project_id=repository.project_id,
            owner_id=owner_id,
        )

        return repository

    def delete_repository(
        self,
        repository_id: int,
        owner_id: int,
    ):

        repository = self.get_repository(
            repository_id=repository_id,
            owner_id=owner_id,
        )

        self.repository_repository.delete(repository)
