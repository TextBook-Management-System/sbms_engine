"""Pydantic schemas for book copies and QR tracking endpoints."""

from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from pydantic import BaseModel, Field


class BookCondition(str, PyEnum):
    """Valid book condition values."""

    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    UNUSABLE = "unusable"


class BookCopyCreate(BaseModel):
    """Request schema for creating a book copy."""

    book_id: int
    school_id: int
    qr_code: str = Field(..., min_length=1, max_length=255)


class BookCopyConditionUpdate(BaseModel):
    """Request schema for updating a book copy's condition."""

    condition: BookCondition


class BookCopyResponse(BaseModel):
    """Response schema for a book copy."""

    id: int
    book_id: int
    school_id: int
    qr_code: str
    condition: str
    created_at: datetime

    model_config = {"from_attributes": True}
