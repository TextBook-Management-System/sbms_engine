"""Pydantic schemas for damage notifications endpoints."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DamageNotificationCreate(BaseModel):
    """Request schema for creating a damage notification."""

    book_copy_id: int
    description: str = Field(..., min_length=1, max_length=1000)


class DamageNotificationResolve(BaseModel):
    """Request schema for resolving a damage notification."""

    resolution_note: str = Field(..., min_length=1, max_length=1000)


class DamageNotificationResponse(BaseModel):
    """Response schema for a damage notification."""

    id: int
    book_copy_id: int
    reported_by: int
    description: str
    status: str
    resolution_note: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
