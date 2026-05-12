"""
Inventory service for read-only inventory queries.

The school_books_inventory table is maintained by MySQL triggers on book_copies.
This service provides read-only access to inventory records.

Validates: Requirements 10.1, 10.2, 10.3, 10.5, 10.6
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.pagination import PaginatedResponse, PaginationParams, paginate
from app.models.database import Book, School, SchoolBooksInventory


def validate_school_exists(db: Session, school_id: int) -> None:
    """Check that the referenced school_id exists. Raise 404 if not.

    Validates: Requirement 10.5
    """
    school = db.query(School).filter(School.id == school_id).first()
    if school is None:
        raise NotFoundError(detail=f"School with id {school_id} not found")


def validate_book_exists(db: Session, book_id: int) -> None:
    """Check that the referenced book_id exists. Raise 404 if not.

    Validates: Requirement 10.6
    """
    book = db.query(Book).filter(Book.id == book_id).first()
    if book is None:
        raise NotFoundError(detail=f"Book with id {book_id} not found")


def get_inventory_list(
    db: Session,
    school_id: int,
    params: PaginationParams,
) -> PaginatedResponse:
    """Get a paginated list of inventory records for a school.

    Validates: Requirement 10.1

    Args:
        db: Database session.
        school_id: The school to query inventory for.
        params: Pagination parameters (page, page_size).

    Returns:
        PaginatedResponse with inventory items.

    Raises:
        NotFoundError: If the school does not exist.
    """
    validate_school_exists(db, school_id)

    query = db.query(SchoolBooksInventory).filter(
        SchoolBooksInventory.school_id == school_id
    )
    return paginate(query, params)


def get_inventory_by_book(
    db: Session,
    school_id: int,
    book_id: int,
) -> SchoolBooksInventory:
    """Get a single inventory record for a specific book at a school.

    Validates: Requirements 10.2, 10.3, 10.5, 10.6

    Args:
        db: Database session.
        school_id: The school to query.
        book_id: The book to look up.

    Returns:
        The inventory record.

    Raises:
        NotFoundError: If the school, book, or inventory record does not exist.
    """
    validate_school_exists(db, school_id)
    validate_book_exists(db, book_id)

    record = (
        db.query(SchoolBooksInventory)
        .filter(
            SchoolBooksInventory.school_id == school_id,
            SchoolBooksInventory.book_id == book_id,
        )
        .first()
    )
    if record is None:
        raise NotFoundError(
            detail=f"No inventory record exists for book {book_id} at school {school_id}"
        )
    return record
