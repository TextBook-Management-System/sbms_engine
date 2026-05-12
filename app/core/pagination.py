"""Reusable pagination dependency and response envelope for all list endpoints."""

from typing import Generic, List, TypeVar

from fastapi import Query
from pydantic import BaseModel
from sqlalchemy.orm import Query as SAQuery

T = TypeVar("T")


class PaginationParams:
    """FastAPI dependency that extracts and validates pagination query parameters.

    Usage:
        @router.get("/items")
        def list_items(params: PaginationParams = Depends()):
            ...

    Attributes:
        page: Current page number (minimum 1, default 1).
        page_size: Number of items per page (minimum 1, capped at 100, default 20).
    """

    def __init__(
        self,
        page: int = Query(default=1, ge=1, description="Page number (starting from 1)"),
        page_size: int = Query(
            default=20, ge=1, description="Number of items per page (max 100)"
        ),
    ):
        self.page = page
        # Cap page_size at 100 if exceeded
        self.page_size = min(page_size, 100)


class PaginatedResponse(BaseModel, Generic[T]):
    """Standardized paginated response envelope.

    Attributes:
        items: List of records for the current page.
        total: Total number of matching records across all pages.
        page: Current page number.
        page_size: Number of items per page (effective, after capping).
    """

    items: List[T]
    total: int
    page: int
    page_size: int


def paginate(query: SAQuery, params: PaginationParams) -> PaginatedResponse:
    """Apply pagination to a SQLAlchemy query and return the response envelope.

    Args:
        query: A SQLAlchemy ORM query to paginate.
        params: PaginationParams instance with page and page_size.

    Returns:
        PaginatedResponse with items, total count, page, and page_size.
    """
    total = query.count()

    offset = (params.page - 1) * params.page_size
    items = query.offset(offset).limit(params.page_size).all()

    return PaginatedResponse(
        items=items,
        total=total,
        page=params.page,
        page_size=params.page_size,
    )
