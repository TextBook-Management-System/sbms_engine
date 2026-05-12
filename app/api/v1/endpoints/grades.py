"""Grades endpoints for managing grades within a school.

Provides:
- POST /schools/{school_id}/grades → create a grade for a school
- GET /schools/{school_id}/grades → paginated list of grades for a school

Validates: Requirements 8.1, 8.2, 8.10
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from starlette.status import HTTP_201_CREATED

from app.core.exceptions import NotFoundError
from app.core.pagination import PaginatedResponse, PaginationParams, paginate
from app.database.session import get_db
from app.models.database import Grade, School
from app.schemas.grades import GradeCreate, GradeResponse

router = APIRouter(prefix="/schools/{school_id}/grades", tags=["grades"])


def _validate_school_exists(db: Session, school_id: int) -> None:
    """Check that the referenced school_id exists. Raise 404 if not."""
    school = db.query(School).filter(School.id == school_id).first()
    if school is None:
        raise NotFoundError(detail=f"School with id {school_id} not found")


@router.post("", response_model=GradeResponse, status_code=HTTP_201_CREATED)
def create_grade(
    school_id: int,
    payload: GradeCreate,
    db: Session = Depends(get_db),
):
    """Create a new grade for the specified school.

    Validates that the school_id references an existing school (404 if not).
    """
    _validate_school_exists(db, school_id)

    grade = Grade(school_id=school_id, name=payload.name)
    db.add(grade)
    db.commit()
    db.refresh(grade)
    return grade


@router.get("", response_model=PaginatedResponse[GradeResponse])
def list_grades(
    school_id: int,
    params: PaginationParams = Depends(),
    db: Session = Depends(get_db),
):
    """List all grades for the specified school with pagination.

    Validates that the school_id references an existing school (404 if not).
    """
    _validate_school_exists(db, school_id)

    query = db.query(Grade).filter(Grade.school_id == school_id)
    return paginate(query, params)
