"""Inventory endpoints for read-only school books inventory.

The school_books_inventory table is maintained by MySQL triggers and is
read-only via the API. Only GET requests are allowed; POST, PUT, and DELETE
return HTTP 405 (Method Not Allowed).

Provides:
- GET /schools/{school_id}/inventory → paginated list of inventory records
- GET /schools/{school_id}/inventory?book_id=X → single inventory record for a book
- POST /schools/{school_id}/inventory → 405 Method Not Allowed
- PUT /schools/{school_id}/inventory → 405 Method Not Allowed
- DELETE /schools/{school_id}/inventory → 405 Method Not Allowed

Validates: Requirements 10.1–10.6
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.pagination import PaginatedResponse, PaginationParams
from app.database.session import get_db
from app.schemas.inventory import InventoryResponse
from app.services import inventory_service

router = APIRouter(prefix="/schools/{school_id}/inventory", tags=["inventory"])


@router.get("", response_model=PaginatedResponse[InventoryResponse])
def list_inventory(
    school_id: int,
    book_id: Optional[int] = Query(default=None, description="Filter by book ID"),
    params: PaginationParams = Depends(),
    db: Session = Depends(get_db),
):
    """List inventory records for a school, or get a single record by book_id.

    If book_id query parameter is provided, returns the single inventory record
    for that book at the specified school (wrapped in paginated response with 1 item).
    Otherwise, returns a paginated list of all inventory records for the school.

    Validates: Requirements 10.1, 10.2, 10.3, 10.5, 10.6
    """
    if book_id is not None:
        # Return single record for the specified book
        record = inventory_service.get_inventory_by_book(db, school_id, book_id)
        return PaginatedResponse(
            items=[record],
            total=1,
            page=1,
            page_size=params.page_size,
        )

    # Return paginated list of all inventory records for the school
    return inventory_service.get_inventory_list(db, school_id, params)


@router.post("")
def create_inventory(school_id: int):
    """POST is not allowed — inventory is maintained by MySQL triggers.

    Validates: Requirement 10.4
    """
    return JSONResponse(
        status_code=405,
        content={
            "detail": "Inventory is read-only. It is maintained by database triggers and cannot be modified via the API.",
            "status_code": 405,
            "error_type": "conflict",
        },
    )


@router.put("")
def update_inventory(school_id: int):
    """PUT is not allowed — inventory is maintained by MySQL triggers.

    Validates: Requirement 10.4
    """
    return JSONResponse(
        status_code=405,
        content={
            "detail": "Inventory is read-only. It is maintained by database triggers and cannot be modified via the API.",
            "status_code": 405,
            "error_type": "conflict",
        },
    )


@router.delete("")
def delete_inventory(school_id: int):
    """DELETE is not allowed — inventory is maintained by MySQL triggers.

    Validates: Requirement 10.4
    """
    return JSONResponse(
        status_code=405,
        content={
            "detail": "Inventory is read-only. It is maintained by database triggers and cannot be modified via the API.",
            "status_code": 405,
            "error_type": "conflict",
        },
    )
