"""Pydantic schemas for replacement requests endpoints."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ReplacementRequestCreate(BaseModel):
    """Request schema for creating a replacement request."""

    damage_notification_id: int


class ReplacementRequestReject(BaseModel):
    """Request schema for rejecting a replacement request."""

    reason: str = Field(..., min_length=1, max_length=1000)


class ReplacementRequestResponse(BaseModel):
    """Response schema for a replacement request."""

    id: int
    damage_notification_id: int
    status: str
    reason: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
