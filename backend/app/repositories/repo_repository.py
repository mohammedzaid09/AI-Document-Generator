from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.repository import Repository


class RepositoryRepository:

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        github_repo_id: int,
        name: str,
        full_name: str,
        url: str,
        default_branch: str,
        project_id: int,
    ) -> Repository:

        repository = Repository(
            github_repo_id=github_repo_id,
            name=name,
            full_name=full_name,
            url=url,
            default_branch=default_branch,
            project_id=project_id,
        )

        self.db.add(repository)
        self.db.commit()
        self.db.refresh(repository)

        return repository

    def get_by_id(
        self,
        repository_id: int,
    ) -> Repository | None:

        return self.db.get(Repository, repository_id)

    def get_by_project(
        self,
        project_id: int,
    ) -> list[Repository]:

        statement = select(Repository).where(
            Repository.project_id == project_id
        )

        return list(self.db.scalars(statement).all())

    def get_by_github_id(
        self,
        github_repo_id: int,
    ) -> Repository | None:

        statement = select(Repository).where(
            Repository.github_repo_id == github_repo_id
        )

        return self.db.scalar(statement)

    def delete(
        self,
        repository: Repository,
    ) -> None:

        self.db.delete(repository)
        self.db.commit()