
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.documentation_generation_service import (
    DocumentationGenerationService,
)


router = APIRouter(
    prefix="/api",
    tags=["Documentation"],
)


@router.post("/repositories/{repository_id}/generate-docs")
def generate_documentation(
    repository_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = DocumentationGenerationService(db)

    try:
        return service.generate_document(
            user_id=current_user.id,
            repository_id=repository_id,
        )

    except HTTPException:
        raise

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except RuntimeError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc


@router.get("/repositories/{repository_id}/documents")
def get_repository_documents(
    repository_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = DocumentationGenerationService(db)

    try:
        return service.get_generated_documents(
            user_id=current_user.id,
            repository_id=repository_id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@router.get("/documents/{document_id}")
def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = DocumentationGenerationService(db)

    try:
        return service.get_generated_document(
            user_id=current_user.id,
            document_id=document_id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

@router.delete("/documents/{document_id}")
def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = DocumentationGenerationService(db)

    try:
        return service.delete_generated_document(
            user_id=current_user.id,
            document_id=document_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
