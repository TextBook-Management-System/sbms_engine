"""API endpoints for subjects (lookup table).

Provides full CRUD operations:
- POST /subjects → create with unique name check (201)
- GET /subjects → paginated list
- GET /subjects/{id} → get by ID
- PUT /subjects/{id} → update with unique name check
- DELETE /subjects/{id} → delete with referential integrity check
"""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.pagination import PaginatedResponse, PaginationParams
from app.database.session import get_db
from app.models.database import Book, Subject
from app.schemas.subjects import SubjectCreate, SubjectResponse, SubjectUpdate
from app.services import crud_service

router = APIRouter(prefix="/subjects", tags=["subjects"])


@router.post("/", response_model=SubjectResponse, status_code=201)
def create_subject(
    payload: SubjectCreate,
    db: Session = Depends(get_db),
):
    """Create a new subject with unique name enforcement."""
    subject = crud_service.create(
        db=db,
        model_class=Subject,
        data=payload.model_dump(),
        unique_fields=["name"],
    )
    return subject


@router.get("/", response_model=PaginatedResponse[SubjectResponse])
def list_subjects(
    params: PaginationParams = Depends(),
    db: Session = Depends(get_db),
):
    """Get a paginated list of all subjects."""
    return crud_service.get_all(
        db=db,
        model_class=Subject,
        params=params,
    )


@router.get("/{id}", response_model=SubjectResponse)
def get_subject(
    id: int,
    db: Session = Depends(get_db),
):
    """Get a subject by ID."""
    return crud_service.get_by_id(db=db, model_class=Subject, id=id)


@router.put("/{id}", response_model=SubjectResponse)
def update_subject(
    id: int,
    payload: SubjectUpdate,
    db: Session = Depends(get_db),
):
    """Update a subject with unique name enforcement."""
    return crud_service.update(
        db=db,
        model_class=Subject,
        id=id,
        data=payload.model_dump(),
        unique_fields=["name"],
    )


@router.delete("/{id}", status_code=204)
def delete_subject(
    id: int,
    db: Session = Depends(get_db),
):
    """Delete a subject with referential integrity check (books reference subjects)."""
    crud_service.delete(
        db=db,
        model_class=Subject,
        id=id,
        check_references=[(Book, "subject_id")],
    )
    return Response(status_code=204)
