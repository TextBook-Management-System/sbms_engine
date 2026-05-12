"""Deliveries and book boxes endpoints for the SBMS API.

Provides endpoints for managing deliveries and their associated book boxes:
- POST /deliveries: Create a delivery (validate approved book_request_id)
- GET /deliveries: List deliveries scoped by role
- GET /deliveries/{id}: Get a delivery by ID (includes book boxes)
- POST /deliveries/{delivery_id}/boxes: Create a book box within a delivery
- GET /deliveries/{delivery_id}/boxes: List book boxes for a delivery

Requirements: 12.1–12.7
"""

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.core.pagination import PaginatedResponse, PaginationParams, paginate
from app.core.rbac import (
    ROLE_DEPT_ADMIN,
    ROLE_SCHOOL_ADMIN,
    Scope,
    get_user_scope,
    require_role,
)
from app.database.session import get_db
from app.models.database import BookBox, BookRequest, Delivery, School, User
from app.schemas.deliveries import (
    BookBoxCreate,
    BookBoxResponse,
    DeliveryCreate,
    DeliveryResponse,
    DeliveryWithBoxesResponse,
)

router = APIRouter(prefix="/deliveries", tags=["deliveries"])


# ---------------------------------------------------------------------------
# Delivery Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=DeliveryResponse,
    status_code=201,
)
def create_delivery(
    payload: DeliveryCreate,
    current_user: User = Depends(require_role(ROLE_DEPT_ADMIN, ROLE_SCHOOL_ADMIN)),
    db: Session = Depends(get_db),
) -> DeliveryResponse:
    """Create a new delivery.

    Validates that book_request_id references an existing book request with status "approved".
    Sets initial delivery status to "pending".
    Returns HTTP 201 on success, HTTP 422 if book_request_id is invalid or not approved.
    """
    # Validate book_request_id exists and has status "approved"
    book_request = (
        db.query(BookRequest)
        .filter(BookRequest.id == payload.book_request_id)
        .first()
    )
    if not book_request:
        raise ValidationError(
            detail=f"Book request with id {payload.book_request_id} not found"
        )
    if book_request.status != "approved":
        raise ValidationError(
            detail=f"Book request with id {payload.book_request_id} is not approved (current status: {book_request.status})"
        )

    delivery = Delivery(
        book_request_id=payload.book_request_id,
        status="pending",
    )
    db.add(delivery)
    db.commit()
    db.refresh(delivery)
    return delivery


@router.get(
    "",
    response_model=PaginatedResponse[DeliveryResponse],
)
def list_deliveries(
    params: PaginationParams = Depends(),
    scope: Scope = Depends(get_user_scope),
    db: Session = Depends(get_db),
) -> PaginatedResponse[DeliveryResponse]:
    """List deliveries scoped by the user's role.

    - DeptAdmin: sees all deliveries for book requests from schools in their department.
    - SchoolAdmin: sees only deliveries for book requests from their own school.
    """
    query = db.query(Delivery)

    if scope.role == ROLE_DEPT_ADMIN and scope.department_id is not None:
        # DeptAdmin sees deliveries for all schools in their department
        school_ids = (
            db.query(School.id)
            .filter(School.department_id == scope.department_id)
            .subquery()
        )
        request_ids = (
            db.query(BookRequest.id)
            .filter(BookRequest.school_id.in_(school_ids))
            .subquery()
        )
        query = query.filter(Delivery.book_request_id.in_(request_ids))
    elif scope.role == ROLE_SCHOOL_ADMIN and scope.school_id is not None:
        # SchoolAdmin sees deliveries for their school's book requests
        request_ids = (
            db.query(BookRequest.id)
            .filter(BookRequest.school_id == scope.school_id)
            .subquery()
        )
        query = query.filter(Delivery.book_request_id.in_(request_ids))
    else:
        # Other roles: return empty (no access to deliveries list)
        query = query.filter(Delivery.id == None)  # noqa: E711

    query = query.order_by(Delivery.created_at.desc())
    return paginate(query, params)


@router.get(
    "/{delivery_id}",
    response_model=DeliveryWithBoxesResponse,
)
def get_delivery(
    delivery_id: int,
    current_user: User = Depends(require_role(ROLE_DEPT_ADMIN, ROLE_SCHOOL_ADMIN)),
    db: Session = Depends(get_db),
) -> DeliveryWithBoxesResponse:
    """Get a delivery by ID, including its associated book boxes.

    Returns HTTP 404 if the delivery does not exist.
    """
    delivery = db.query(Delivery).filter(Delivery.id == delivery_id).first()
    if not delivery:
        raise NotFoundError(detail=f"Delivery with id {delivery_id} not found")
    return delivery


# ---------------------------------------------------------------------------
# Book Box Endpoints (sub-resource of deliveries)
# ---------------------------------------------------------------------------


@router.post(
    "/{delivery_id}/boxes",
    response_model=BookBoxResponse,
    status_code=201,
)
def create_book_box(
    delivery_id: int,
    payload: BookBoxCreate,
    current_user: User = Depends(require_role(ROLE_DEPT_ADMIN, ROLE_SCHOOL_ADMIN)),
    db: Session = Depends(get_db),
) -> BookBoxResponse:
    """Create a book box within a delivery.

    Validates that the delivery exists. Returns HTTP 404 if not found.
    Returns HTTP 201 on success.
    """
    # Validate delivery exists
    delivery = db.query(Delivery).filter(Delivery.id == delivery_id).first()
    if not delivery:
        raise NotFoundError(detail=f"Delivery with id {delivery_id} not found")

    book_box = BookBox(
        delivery_id=delivery_id,
        book_id=payload.book_id,
        quantity=payload.quantity,
    )
    db.add(book_box)
    db.commit()
    db.refresh(book_box)
    return book_box


@router.get(
    "/{delivery_id}/boxes",
    response_model=List[BookBoxResponse],
)
def list_book_boxes(
    delivery_id: int,
    current_user: User = Depends(require_role(ROLE_DEPT_ADMIN, ROLE_SCHOOL_ADMIN)),
    db: Session = Depends(get_db),
) -> List[BookBoxResponse]:
    """List all book boxes for a delivery.

    Validates that the delivery exists. Returns HTTP 404 if not found.
    """
    # Validate delivery exists
    delivery = db.query(Delivery).filter(Delivery.id == delivery_id).first()
    if not delivery:
        raise NotFoundError(detail=f"Delivery with id {delivery_id} not found")

    boxes = db.query(BookBox).filter(BookBox.delivery_id == delivery_id).all()
    return boxes
