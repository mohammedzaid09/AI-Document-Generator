from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.project_repository import ProjectRepository
from app.repositories.workspace_repository import WorkspaceRepository


class ProjectService:

    def __init__(self, db: Session):
        self.project_repository = ProjectRepository(db)
        self.workspace_repository = WorkspaceRepository(db)

    def create_project(
        self,
        name: str,
        description: str | None,
        workspace_id: int,
        owner_id: int,
    ):

        workspace = self.workspace_repository.get_by_id(
            workspace_id
        )

        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found",
            )

        if workspace.owner_id != owner_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this workspace",
            )

        return self.project_repository.create(
            name=name,
            description=description,
            workspace_id=workspace_id,
        )

    def get_workspace_projects(
        self,
        workspace_id: int,
        owner_id: int,
    ):

        workspace = self.workspace_repository.get_by_id(
            workspace_id
        )

        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found",
            )

        if workspace.owner_id != owner_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this workspace",
            )

        return self.project_repository.get_by_workspace(
            workspace_id
        )

    def get_project(
        self,
        project_id: int,
        owner_id: int,
    ):

        project = self.project_repository.get_by_id(
            project_id
        )

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

    def delete_project(
        self,
        project_id: int,
        owner_id: int,
    ):

        project = self.get_project(
            project_id=project_id,
            owner_id=owner_id,
        )

        self.project_repository.delete(project)