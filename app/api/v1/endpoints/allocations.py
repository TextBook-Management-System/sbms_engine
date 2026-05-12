"""Book allocations endpoints.

Provides endpoints for creating book-to-learner allocations, processing returns,
and listing/retrieving allocation records with optional filters.

Enforces:
- Mutual exclusivity: cannot allocate an already-active book copy (409)
- Status transition: only active → returned (409 if already returned)

Validates: Requirements 16.1–16.8
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from starlette.status import HTTP_201_CREATED

from app.core.pagination import PaginatedResponse, PaginationParams
from app.database.session import get_db
from app.schemas.allocations import AllocationCreate, AllocationResponse
from app.services import allocation_service

router = APIRouter(prefix="/allocations", tags=["allocations"])


@router.post("", response_model=AllocationResponse, status_code=HTTP_201_CREATED)
def create_allocation(payload: AllocationCreate, db: Session = Depends(get_db)):
    """Create a new book allocation.

    Allocates a book copy to a learner with status "active".
    Returns 404 if book_copy_id or learner_id does not exist.
    Returns 409 if the book copy already has an active allocation.
    """
    allocation = allocation_service.allocate(
        db=db,
        book_copy_id=payload.book_copy_id,
        learner_id=payload.learner_id,
    )
    return allocation


@router.get("", response_model=PaginatedResponse[AllocationResponse])
def list_allocations(
    learner_id: Optional[int] = Query(default=None, description="Filter by learner"),
    book_copy_id: Optional[int] = Query(default=None, description="Filter by book copy"),
    status: Optional[str] = Query(default=None, description="Filter by status (active or returned)"),
    params: PaginationParams = Depends(),
    db: Session = Depends(get_db),
):
    """List allocations with optional filters and pagination.

    Supports filtering by learner_id, book_copy_id, and status.
    """
    return allocation_service.list_allocations(
        db=db,
        params=params,
        learner_id=learner_id,
        book_copy_id=book_copy_id,
        status=status,
    )


@router.get("/{id}", response_model=AllocationResponse)
def get_allocation(id: int, db: Session = Depends(get_db)):
    """Get an allocation by ID. Returns 404 if not found."""
    return allocation_service.get_by_id(db, id)


@router.put("/{id}/return", response_model=AllocationResponse)
def return_allocation(id: int, db: Session = Depends(get_db)):
    """Process a book return.

    Updates the allocation status to "returned" and sets the return_date.
    Returns 404 if allocation not found.
    Returns 409 if the allocation is not in "active" status.
    """
    return allocation_service.return_allocation(db, id)
