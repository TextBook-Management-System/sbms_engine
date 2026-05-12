"""Book requests endpoints for the SBMS API.

Provides CRUD operations for book requests with role-based access control:
- POST /book-requests: Create a new book request (SchoolAdmin, DeptAdmin)
- GET /book-requests: List book requests scoped by role
- GET /book-requests/{id}: Get a book request by ID
- PUT /book-requests/{id}/approve: Approve a pending request (DeptAdmin only)
- PUT /book-requests/{id}/reject: Reject a pending request (DeptAdmin only)
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.pagination import PaginatedResponse, PaginationParams, paginate
from app.core.rbac import (
    ROLE_DEPT_ADMIN,
    ROLE_SCHOOL_ADMIN,
    Scope,
    get_user_scope,
    require_role,
)
from app.database.session import get_db
from app.models.database import Book, BookRequest, School, User
from app.schemas.book_requests import (
    BookRequestCreate,
    BookRequestReject,
    BookRequestResponse,
)

router = APIRouter(prefix="/book-requests", tags=["book-requests"])


@router.post(
    "",
    response_model=BookRequestResponse,
    status_code=201,
)
def create_book_request(
    payload: BookRequestCreate,
    current_user: User = Depends(require_role(ROLE_DEPT_ADMIN, ROLE_SCHOOL_ADMIN)),
    db: Session = Depends(get_db),
) -> BookRequestResponse:
    """Create a new book request.

    Validates that the referenced book_id and school_id exist.
    Sets initial status to "pending".
    """
    # Validate book_id exists
    book = db.query(Book).filter(Book.id == payload.book_id).first()
    if not book:
        raise ValidationError(detail=f"Book with id {payload.book_id} not found")

    # Validate school_id exists
    school = db.query(School).filter(School.id == payload.school_id).first()
    if not school:
        raise ValidationError(detail=f"School with id {payload.school_id} not found")

    book_request = BookRequest(
        book_id=payload.book_id,
        school_id=payload.school_id,
        quantity=payload.quantity,
        status="pending",
        reason=payload.reason,
    )
    db.add(book_request)
    db.commit()
    db.refresh(book_request)
    return book_request


@router.get(
    "",
    response_model=PaginatedResponse[BookRequestResponse],
)
def list_book_requests(
    params: PaginationParams = Depends(),
    scope: Scope = Depends(get_user_scope),
    db: Session = Depends(get_db),
) -> PaginatedResponse[BookRequestResponse]:
    """List book requests scoped by the user's role.

    - DeptAdmin: sees all requests for schools in their department.
    - SchoolAdmin: sees only requests from their own school.
    """
    query = db.query(BookRequest)

    if scope.role == ROLE_DEPT_ADMIN and scope.department_id is not None:
        # DeptAdmin sees all requests for schools in their department
        school_ids = (
            db.query(School.id)
            .filter(School.department_id == scope.department_id)
            .subquery()
        )
        query = query.filter(BookRequest.school_id.in_(school_ids))
    elif scope.role == ROLE_SCHOOL_ADMIN and scope.school_id is not None:
        # SchoolAdmin sees only their school's requests
        query = query.filter(BookRequest.school_id == scope.school_id)
    else:
        # Other roles: return empty (no access to book requests list)
        query = query.filter(BookRequest.id == None)  # noqa: E711

    query = query.order_by(BookRequest.created_at.desc())
    return paginate(query, params)


@router.get(
    "/{request_id}",
    response_model=BookRequestResponse,
)
def get_book_request(
    request_id: int,
    current_user: User = Depends(require_role(ROLE_DEPT_ADMIN, ROLE_SCHOOL_ADMIN)),
    db: Session = Depends(get_db),
) -> BookRequestResponse:
    """Get a book request by ID."""
    book_request = (
        db.query(BookRequest).filter(BookRequest.id == request_id).first()
    )
    if not book_request:
        raise NotFoundError(detail=f"Book request with id {request_id} not found")
    return book_request


@router.put(
    "/{request_id}/approve",
    response_model=BookRequestResponse,
)
def approve_book_request(
    request_id: int,
    current_user: User = Depends(require_role(ROLE_DEPT_ADMIN)),
    db: Session = Depends(get_db),
) -> BookRequestResponse:
    """Approve a pending book request. DeptAdmin only.

    Returns 409 if the request is not in "pending" status.
    """
    book_request = (
        db.query(BookRequest).filter(BookRequest.id == request_id).first()
    )
    if not book_request:
        raise NotFoundError(detail=f"Book request with id {request_id} not found")

    if book_request.status != "pending":
        raise ConflictError(
            detail=f"Book request has already been {book_request.status}. Only pending requests can be approved."
        )

    book_request.status = "approved"
    db.commit()
    db.refresh(book_request)
    return book_request


@router.put(
    "/{request_id}/reject",
    response_model=BookRequestResponse,
)
def reject_book_request(
    request_id: int,
    payload: BookRequestReject,
    current_user: User = Depends(require_role(ROLE_DEPT_ADMIN)),
    db: Session = Depends(get_db),
) -> BookRequestResponse:
    """Reject a pending book request. DeptAdmin only.

    Requires a reason (1-1000 characters).
    Returns 409 if the request is not in "pending" status.
    """
    book_request = (
        db.query(BookRequest).filter(BookRequest.id == request_id).first()
    )
    if not book_request:
        raise NotFoundError(detail=f"Book request with id {request_id} not found")

    if book_request.status != "pending":
        raise ConflictError(
            detail=f"Book request has already been {book_request.status}. Only pending requests can be rejected."
        )

    book_request.status = "rejected"
    book_request.reason = payload.reason
    db.commit()
    db.refresh(book_request)
    return book_request
