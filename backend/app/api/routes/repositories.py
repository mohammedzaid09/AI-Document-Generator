from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.repository import (
    RepositoryCreate,
    RepositoryResponse,
)
from app.services.repo_service import RepositoryService


router = APIRouter(
    prefix="/api",
    tags=["Repositories"],
)


@router.post(
    "/projects/{project_id}/repositories",
    response_model=RepositoryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_repository(
    project_id: int,
    request: RepositoryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = RepositoryService(db)

    return service.create_repository(
        project_id=project_id,
        owner_id=current_user.id,
        github_owner=request.owner,
        github_repo=request.repo,
)


@router.get(
    "/projects/{project_id}/repositories",
    response_model=list[RepositoryResponse],
)
def get_project_repositories(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = RepositoryService(db)

    return service.get_project_repositories(
        project_id=project_id,
        owner_id=current_user.id,
    )


@router.get(
    "/repositories/{repository_id}",
    response_model=RepositoryResponse,
)
def get_repository(
    repository_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = RepositoryService(db)

    return service.get_repository(
        repository_id=repository_id,
        owner_id=current_user.id,
    )


@router.delete(
    "/repositories/{repository_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_repository(
    repository_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = RepositoryService(db)

    service.delete_repository(
        repository_id=repository_id,
        owner_id=current_user.id,
    )