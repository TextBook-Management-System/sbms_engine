"""Pydantic schemas for book requests endpoints."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class BookRequestCreate(BaseModel):
    """Request schema for creating a book request."""

    book_id: int
    school_id: int
    quantity: int = Field(..., ge=1, le=10000)
    reason: Optional[str] = Field(None, max_length=1000)


class BookRequestReject(BaseModel):
    """Request schema for rejecting a book request."""

    reason: str = Field(..., min_length=1, max_length=1000)


class BookRequestResponse(BaseModel):
    """Response schema for a book request."""

    id: int
    book_id: int
    school_id: int
    quantity: int
    status: str
    reason: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
