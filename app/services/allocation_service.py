"""
Allocation service for book-to-learner assignments and returns.

Handles creating allocations (with mutual exclusivity enforcement),
processing returns (with status transition enforcement), and listing/retrieving
allocation records.

Validates: Requirements 16.1–16.8
"""

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.core.pagination import PaginatedResponse, PaginationParams, paginate
from app.models.database import BookAllocation, BookCopy, Learner


def _validate_book_copy_exists(db: Session, book_copy_id: int) -> None:
    """Check that the referenced book_copy_id exists. Raise 404 if not."""
    existing = db.query(BookCopy).filter(BookCopy.id == book_copy_id).first()
    if existing is None:
        raise NotFoundError(
            detail=f"Book copy with id {book_copy_id} not found"
        )


def _validate_learner_exists(db: Session, learner_id: int) -> None:
    """Check that the referenced learner_id exists. Raise 404 if not."""
    existing = db.query(Learner).filter(Learner.id == learner_id).first()
    if existing is None:
        raise NotFoundError(
            detail=f"Learner with id {learner_id} not found"
        )


def _check_active_allocation(db: Session, book_copy_id: int) -> None:
    """Check that the book copy does not already have an active allocation.

    Raises ConflictError (409) if an active allocation exists for this book copy.
    """
    active = (
        db.query(BookAllocation)
        .filter(
            BookAllocation.book_copy_id == book_copy_id,
            BookAllocation.status == "active",
        )
        .first()
    )
    if active is not None:
        raise ConflictError(
            detail="This book copy is currently allocated. Cannot create a new allocation until the existing one is returned."
        )


def allocate(
    db: Session,
    book_copy_id: int,
    learner_id: int,
) -> BookAllocation:
    """Create a new book allocation.

    Validates that both book_copy_id and learner_id exist, and that the book copy
    does not already have an active allocation.

    Args:
        db: Database session.
        book_copy_id: ID of the book copy to allocate.
        learner_id: ID of the learner receiving the book.

    Returns:
        The newly created BookAllocation instance with status "active".

    Raises:
        NotFoundError: If book_copy_id or learner_id does not exist (404).
        ConflictError: If the book copy already has an active allocation (409).
    """
    _validate_book_copy_exists(db, book_copy_id)
    _validate_learner_exists(db, learner_id)
    _check_active_allocation(db, book_copy_id)

    allocation = BookAllocation(
        book_copy_id=book_copy_id,
        learner_id=learner_id,
        status="active",
    )
    db.add(allocation)
    db.commit()
    db.refresh(allocation)
    return allocation


def return_allocation(db: Session, allocation_id: int) -> BookAllocation:
    """Process a book return by updating the allocation status.

    Only allocations with status "active" can be returned. Attempting to return
    an already-returned allocation results in a 409 conflict.

    Args:
        db: Database session.
        allocation_id: ID of the allocation to return.

    Returns:
        The updated BookAllocation instance with status "returned" and return_date set.

    Raises:
        NotFoundError: If no allocation with the given ID exists (404).
        ConflictError: If the allocation status is not "active" (409).
    """
    allocation = get_by_id(db, allocation_id)

    if allocation.status != "active":
        raise ConflictError(
            detail="This allocation has already been returned"
        )

    allocation.status = "returned"
    allocation.return_date = datetime.utcnow()
    db.commit()
    db.refresh(allocation)
    return allocation


def get_by_id(db: Session, allocation_id: int) -> BookAllocation:
    """Get an allocation by its ID.

    Args:
        db: Database session.
        allocation_id: Primary key of the allocation.

    Returns:
        The BookAllocation instance.

    Raises:
        NotFoundError: If no allocation with the given ID exists (404).
    """
    allocation = (
        db.query(BookAllocation)
        .filter(BookAllocation.id == allocation_id)
        .first()
    )
    if allocation is None:
        raise NotFoundError(
            detail=f"Allocation with id {allocation_id} not found"
        )
    return allocation


def list_allocations(
    db: Session,
    params: PaginationParams,
    learner_id: Optional[int] = None,
    book_copy_id: Optional[int] = None,
    status: Optional[str] = None,
) -> PaginatedResponse:
    """Get a paginated list of allocations with optional filters.

    Args:
        db: Database session.
        params: Pagination parameters.
        learner_id: Optional filter by learner.
        book_copy_id: Optional filter by book copy.
        status: Optional filter by status ("active" or "returned").

    Returns:
        PaginatedResponse with allocation records.
    """
    query = db.query(BookAllocation)

    if learner_id is not None:
        query = query.filter(BookAllocation.learner_id == learner_id)
    if book_copy_id is not None:
        query = query.filter(BookAllocation.book_copy_id == book_copy_id)
    if status is not None:
        query = query.filter(BookAllocation.status == status)

    return paginate(query, params)
