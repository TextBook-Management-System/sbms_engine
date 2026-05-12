"""Books catalog endpoints with full CRUD, FK validation, and query filtering.

Provides:
- POST /books → Create a book (validates subject_id, grade_level_id FKs, enforces unique ISBN)
- GET /books → Paginated list with optional subject_id and grade_level_id filters
- GET /books/{id} → Single book by ID (404 if not found)
- PUT /books/{id} → Update a book (validates FKs if provided, enforces unique ISBN)
- DELETE /books/{id} → Delete a book (409 if referenced by book_copies)

Validates: Requirements 9.1–9.11
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from starlette.status import HTTP_201_CREATED, HTTP_204_NO_CONTENT

from app.core.exceptions import ValidationError
from app.core.pagination import PaginatedResponse, PaginationParams
from app.database.session import get_db
from app.models.database import Book, BookCopy, GradeLevel, Subject
from app.schemas.books import BookCreate, BookResponse, BookUpdate
from app.services import crud_service

router = APIRouter(prefix="/books", tags=["books"])


def _validate_subject_exists(db: Session, subject_id: int) -> None:
    """Check that the referenced subject_id exists. Raise 422 if not."""
    existing = db.query(Subject).filter(Subject.id == subject_id).first()
    if existing is None:
        raise ValidationError("Referenced subject does not exist")


def _validate_grade_level_exists(db: Session, grade_level_id: int) -> None:
    """Check that the referenced grade_level_id exists. Raise 422 if not."""
    existing = db.query(GradeLevel).filter(GradeLevel.id == grade_level_id).first()
    if existing is None:
        raise ValidationError("Referenced grade level does not exist")


@router.post("", response_model=BookResponse, status_code=HTTP_201_CREATED)
def create_book(payload: BookCreate, db: Session = Depends(get_db)):
    """Create a new book.

    Validates that subject_id and grade_level_id reference existing records (422 if not).
    Enforces unique ISBN constraint (409 if duplicate).

    Requirements: 9.1, 9.10, 9.11
    """
    _validate_subject_exists(db, payload.subject_id)
    _validate_grade_level_exists(db, payload.grade_level_id)
    data = payload.model_dump()
    book = crud_service.create(db, Book, data, unique_fields=["isbn"])
    return book


@router.get("", response_model=PaginatedResponse[BookResponse])
def list_books(
    subject_id: Optional[int] = Query(default=None, description="Filter by subject"),
    grade_level_id: Optional[int] = Query(
        default=None, description="Filter by grade level"
    ),
    params: PaginationParams = Depends(),
    db: Session = Depends(get_db),
):
    """List all books with optional filters and pagination.

    Supports filtering by subject_id, grade_level_id, or both.

    Requirements: 9.2, 9.3, 9.4, 9.5
    """
    filters = {"subject_id": subject_id, "grade_level_id": grade_level_id}
    return crud_service.get_all(db, Book, params, filters=filters)


@router.get("/{id}", response_model=BookResponse)
def get_book(id: int, db: Session = Depends(get_db)):
    """Get a book by ID.

    Returns 404 if the book does not exist.

    Requirements: 9.6, 9.9
    """
    return crud_service.get_by_id(db, Book, id)


@router.put("/{id}", response_model=BookResponse)
def update_book(id: int, payload: BookUpdate, db: Session = Depends(get_db)):
    """Update a book by ID.

    Validates FK references if subject_id or grade_level_id are provided (422 if invalid).
    Enforces unique ISBN constraint (409 if duplicate).
    Returns 404 if the book does not exist.

    Requirements: 9.7, 9.9, 9.10, 9.11
    """
    data = payload.model_dump(exclude_unset=True)
    if "subject_id" in data and data["subject_id"] is not None:
        _validate_subject_exists(db, data["subject_id"])
    if "grade_level_id" in data and data["grade_level_id"] is not None:
        _validate_grade_level_exists(db, data["grade_level_id"])
    book = crud_service.update(db, Book, id, data, unique_fields=["isbn"])
    return book


@router.delete("/{id}", status_code=HTTP_204_NO_CONTENT)
def delete_book(id: int, db: Session = Depends(get_db)):
    """Delete a book by ID.

    Returns 404 if the book does not exist.
    Returns 409 if the book is referenced by book_copies records.

    Requirements: 9.8, 9.9
    """
    crud_service.delete(db, Book, id, check_references=[(BookCopy, "book_id")])
    return None
