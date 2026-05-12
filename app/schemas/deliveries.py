"""Pydantic schemas for deliveries and book boxes endpoints."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class DeliveryCreate(BaseModel):
    """Request schema for creating a delivery."""

    book_request_id: int


class DeliveryResponse(BaseModel):
    """Response schema for a delivery."""

    id: int
    book_request_id: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class BookBoxCreate(BaseModel):
    """Request schema for creating a book box within a delivery."""

    book_id: int
    quantity: int = Field(..., ge=1)


class BookBoxResponse(BaseModel):
    """Response schema for a book box."""

    id: int
    delivery_id: int
    book_id: int
    quantity: int

    model_config = {"from_attributes": True}


class DeliveryWithBoxesResponse(BaseModel):
    """Response schema for a delivery including its associated book boxes."""

    id: int
    book_request_id: int
    status: str
    created_at: datetime
    book_boxes: List[BookBoxResponse] = []

    model_config = {"from_attributes": True}
