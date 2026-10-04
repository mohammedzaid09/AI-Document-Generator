from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.workspace_repository import WorkspaceRepository


class WorkspaceService:

    def __init__(self, db: Session):
        self.workspace_repository = WorkspaceRepository(db)

    def create_workspace(
        self,
        name: str,
        owner_id: int,
    ):
        return self.workspace_repository.create(
            name=name,
            owner_id=owner_id,
        )

    def get_user_workspaces(
        self,
        owner_id: int,
    ):
        return self.workspace_repository.get_by_owner(
            owner_id=owner_id,
        )

    def get_workspace(
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

        return workspace

    def delete_workspace(
        self,
        workspace_id: int,
        owner_id: int,
    ):
        workspace = self.get_workspace(
            workspace_id=workspace_id,
            owner_id=owner_id,
        )

        self.workspace_repository.delete(workspace)