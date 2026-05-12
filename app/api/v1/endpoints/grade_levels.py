"""API endpoints for grade levels (lookup table).

Provides full CRUD operations:
- POST /grade-levels → create with unique name check (201)
- GET /grade-levels → paginated list
- GET /grade-levels/{id} → get by ID
- PUT /grade-levels/{id} → update with unique name check
- DELETE /grade-levels/{id} → delete with referential integrity check
"""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.pagination import PaginatedResponse, PaginationParams
from app.database.session import get_db
from app.models.database import Book, GradeLevel
from app.schemas.grade_levels import GradeLevelCreate, GradeLevelResponse, GradeLevelUpdate
from app.services import crud_service

router = APIRouter(prefix="/grade-levels", tags=["grade-levels"])


@router.post("/", response_model=GradeLevelResponse, status_code=201)
def create_grade_level(
    payload: GradeLevelCreate,
    db: Session = Depends(get_db),
):
    """Create a new grade level with unique name enforcement."""
    grade_level = crud_service.create(
        db=db,
        model_class=GradeLevel,
        data=payload.model_dump(),
        unique_fields=["name"],
    )
    return grade_level


@router.get("/", response_model=PaginatedResponse[GradeLevelResponse])
def list_grade_levels(
    params: PaginationParams = Depends(),
    db: Session = Depends(get_db),
):
    """Get a paginated list of all grade levels."""
    return crud_service.get_all(
        db=db,
        model_class=GradeLevel,
        params=params,
    )


@router.get("/{id}", response_model=GradeLevelResponse)
def get_grade_level(
    id: int,
    db: Session = Depends(get_db),
):
    """Get a grade level by ID."""
    return crud_service.get_by_id(db=db, model_class=GradeLevel, id=id)


@router.put("/{id}", response_model=GradeLevelResponse)
def update_grade_level(
    id: int,
    payload: GradeLevelUpdate,
    db: Session = Depends(get_db),
):
    """Update a grade level with unique name enforcement."""
    return crud_service.update(
        db=db,
        model_class=GradeLevel,
        id=id,
        data=payload.model_dump(),
        unique_fields=["name"],
    )


@router.delete("/{id}", status_code=204)
def delete_grade_level(
    id: int,
    db: Session = Depends(get_db),
):
    """Delete a grade level with referential integrity check (books reference grade_levels)."""
    crud_service.delete(
        db=db,
        model_class=GradeLevel,
        id=id,
        check_references=[(Book, "grade_level_id")],
    )
    return Response(status_code=204)
