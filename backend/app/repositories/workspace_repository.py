from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.workspace import Workspace


class WorkspaceRepository:

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        name: str,
        owner_id: int,
    ) -> Workspace:

        workspace = Workspace(
            name=name,
            owner_id=owner_id,
        )

        self.db.add(workspace)
        self.db.commit()
        self.db.refresh(workspace)

        return workspace

    def get_by_id(
        self,
        workspace_id: int,
    ) -> Workspace | None:

        return self.db.get(Workspace, workspace_id)

    def get_by_owner(
        self,
        owner_id: int,
    ) -> list[Workspace]:

        statement = select(Workspace).where(
            Workspace.owner_id == owner_id
        )

        return list(self.db.scalars(statement).all())

    def delete(
        self,
        workspace: Workspace,
    ) -> None:

        self.db.delete(workspace)
        self.db.commit()