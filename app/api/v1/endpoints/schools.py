"""Schools endpoints with full CRUD, department_id FK validation, and query filtering.

Validates: Requirements 4.1–4.8
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from starlette.status import HTTP_201_CREATED, HTTP_204_NO_CONTENT

from app.core.exceptions import ValidationError
from app.core.pagination import PaginatedResponse, PaginationParams
from app.database.session import get_db
from app.models.database import Department, School
from app.schemas.schools import SchoolCreate, SchoolResponse, SchoolUpdate
from app.services import crud_service

router = APIRouter(prefix="/schools", tags=["schools"])


def _validate_department_exists(db: Session, department_id: int) -> None:
    """Check that the referenced department_id exists. Raise 422 if not."""
    existing = db.query(Department).filter(Department.id == department_id).first()
    if existing is None:
        raise ValidationError("Referenced department does not exist")


@router.post("", response_model=SchoolResponse, status_code=HTTP_201_CREATED)
def create_school(payload: SchoolCreate, db: Session = Depends(get_db)):
    """Create a new school. Validates that department_id references an existing department."""
    _validate_department_exists(db, payload.department_id)
    data = payload.model_dump()
    school = crud_service.create(db, School, data)
    return school


@router.get("", response_model=PaginatedResponse[SchoolResponse])
def list_schools(
    department_id: Optional[int] = Query(default=None, description="Filter by department"),
    params: PaginationParams = Depends(),
    db: Session = Depends(get_db),
):
    """List all schools with optional department_id filter and pagination."""
    filters = {"department_id": department_id}
    return crud_service.get_all(db, School, params, filters=filters)


@router.get("/{id}", response_model=SchoolResponse)
def get_school(id: int, db: Session = Depends(get_db)):
    """Get a school by ID."""
    return crud_service.get_by_id(db, School, id)


@router.put("/{id}", response_model=SchoolResponse)
def update_school(id: int, payload: SchoolUpdate, db: Session = Depends(get_db)):
    """Update a school. Validates department_id FK if provided."""
    data = payload.model_dump(exclude_unset=True)
    if "department_id" in data and data["department_id"] is not None:
        _validate_department_exists(db, data["department_id"])
    school = crud_service.update(db, School, id, data)
    return school


@router.delete("/{id}", status_code=HTTP_204_NO_CONTENT)
def delete_school(id: int, db: Session = Depends(get_db)):
    """Delete a school by ID."""
    crud_service.delete(db, School, id)
    return None
