from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import Project


class ProjectRepository:

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        name: str,
        description: str | None,
        workspace_id: int,
    ) -> Project:

        project = Project(
            name=name,
            description=description,
            workspace_id=workspace_id,
        )

        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)

        return project

    def get_by_id(
        self,
        project_id: int,
    ) -> Project | None:

        return self.db.get(Project, project_id)

    def get_by_workspace(
        self,
        workspace_id: int,
    ) -> list[Project]:

        statement = select(Project).where(
            Project.workspace_id == workspace_id
        )

        return list(self.db.scalars(statement).all())

    def delete(
        self,
        project: Project,
    ) -> None:

        self.db.delete(project)
        self.db.commit()