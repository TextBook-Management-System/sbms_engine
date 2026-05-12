"""Departments CRUD endpoints.

Provides full CRUD for department records with:
- Unique name enforcement on create and update (409 on conflict)
- Referential integrity check on delete (409 if schools reference the department)
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.pagination import PaginatedResponse, PaginationParams
from app.database.session import get_db
from app.models.database import Department, School
from app.schemas.departments import DepartmentCreate, DepartmentResponse, DepartmentUpdate
from app.services import crud_service

router = APIRouter(prefix="/departments", tags=["departments"])


@router.post(
    "",
    response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_department(
    payload: DepartmentCreate,
    db: Session = Depends(get_db),
):
    """Create a new department. Name must be unique."""
    department = crud_service.create(
        db=db,
        model_class=Department,
        data=payload.model_dump(),
        unique_fields=["name"],
    )
    return department


@router.get(
    "",
    response_model=PaginatedResponse[DepartmentResponse],
)
def list_departments(
    params: PaginationParams = Depends(),
    db: Session = Depends(get_db),
):
    """Return a paginated list of all departments."""
    return crud_service.get_all(db=db, model_class=Department, params=params)


@router.get(
    "/{id}",
    response_model=DepartmentResponse,
)
def get_department(
    id: int,
    db: Session = Depends(get_db),
):
    """Get a single department by ID."""
    return crud_service.get_by_id(db=db, model_class=Department, id=id)


@router.put(
    "/{id}",
    response_model=DepartmentResponse,
)
def update_department(
    id: int,
    payload: DepartmentUpdate,
    db: Session = Depends(get_db),
):
    """Update a department. Name must remain unique."""
    return crud_service.update(
        db=db,
        model_class=Department,
        id=id,
        data=payload.model_dump(),
        unique_fields=["name"],
    )


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_department(
    id: int,
    db: Session = Depends(get_db),
):
    """Delete a department. Fails with 409 if schools are still associated."""
    crud_service.delete(
        db=db,
        model_class=Department,
        id=id,
        check_references=[(School, "department_id")],
    )
