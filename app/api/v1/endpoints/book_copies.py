"""Book copies and QR tracking endpoints.

Provides CRUD operations for individual book copies tracked by QR code,
including creation with FK validation, lookup by QR code, condition updates,
and paginated listing with filters.

Validates: Requirements 13.1–13.11
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from starlette.status import HTTP_201_CREATED

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.pagination import PaginatedResponse, PaginationParams, paginate
from app.database.session import get_db
from app.models.database import Book, BookCopy, School
from app.schemas.book_copies import (
    BookCopyConditionUpdate,
    BookCopyCreate,
    BookCopyResponse,
)
from app.services import crud_service

router = APIRouter(prefix="/book-copies", tags=["book-copies"])


def _validate_book_exists(db: Session, book_id: int) -> None:
    """Check that the referenced book_id exists. Raise 422 if not."""
    existing = db.query(Book).filter(Book.id == book_id).first()
    if existing is None:
        raise ValidationError("Referenced book does not exist")


def _validate_school_exists(db: Session, school_id: int) -> None:
    """Check that the referenced school_id exists. Raise 422 if not."""
    existing = db.query(School).filter(School.id == school_id).first()
    if existing is None:
        raise ValidationError("Referenced school does not exist")


@router.post("", response_model=BookCopyResponse, status_code=HTTP_201_CREATED)
def create_book_copy(payload: BookCopyCreate, db: Session = Depends(get_db)):
    """Create a new book copy with QR code tracking.

    Validates that book_id and school_id reference existing records (422 if not).
    Enforces unique qr_code constraint (409 if duplicate).
    Defaults condition to "good" on creation.
    """
    _validate_book_exists(db, payload.book_id)
    _validate_school_exists(db, payload.school_id)

    data = payload.model_dump()
    data["condition"] = "good"  # Default condition on creation

    book_copy = crud_service.create(db, BookCopy, data, unique_fields=["qr_code"])
    return book_copy


@router.get("", response_model=PaginatedResponse[BookCopyResponse])
def list_book_copies(
    school_id: Optional[int] = Query(default=None, description="Filter by school"),
    book_id: Optional[int] = Query(default=None, description="Filter by book"),
    params: PaginationParams = Depends(),
    db: Session = Depends(get_db),
):
    """List book copies with optional school_id and book_id filters and pagination."""
    filters = {"school_id": school_id, "book_id": book_id}
    return crud_service.get_all(db, BookCopy, params, filters=filters)


@router.get("/qr/{qr_code}", response_model=BookCopyResponse)
def get_book_copy_by_qr(qr_code: str, db: Session = Depends(get_db)):
    """Get a book copy by its QR code. Returns 404 if not found."""
    book_copy = db.query(BookCopy).filter(BookCopy.qr_code == qr_code).first()
    if book_copy is None:
        raise NotFoundError(detail=f"Book copy with qr_code '{qr_code}' not found")
    return book_copy


@router.get("/{id}", response_model=BookCopyResponse)
def get_book_copy(id: int, db: Session = Depends(get_db)):
    """Get a book copy by ID. Returns 404 if not found."""
    return crud_service.get_by_id(db, BookCopy, id)


@router.put("/{id}/condition", response_model=BookCopyResponse)
def update_book_copy_condition(
    id: int, payload: BookCopyConditionUpdate, db: Session = Depends(get_db)
):
    """Update a book copy's condition.

    Condition must be one of: excellent, good, fair, poor, unusable.
    Returns 422 if invalid value (handled by Pydantic enum validation).
    Returns 404 if book copy not found.
    """
    data = {"condition": payload.condition.value}
    return crud_service.update(db, BookCopy, id, data)
