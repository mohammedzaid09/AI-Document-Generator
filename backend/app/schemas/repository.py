from datetime import datetime

from pydantic import BaseModel


class RepositoryCreate(BaseModel):
    owner: str
    repo: str


class RepositoryResponse(BaseModel):
    id: int
    github_repo_id: int
    name: str
    full_name: str
    url: str
    default_branch: str
    project_id: int
    created_at: datetime

    class Config:
        from_attributes = True