"""Pydantic schemas for departments endpoints."""

from datetime import datetime

from pydantic import BaseModel, Field


class DepartmentCreate(BaseModel):
    """Request schema for creating a department."""

    name: str = Field(..., min_length=1, max_length=200)


class DepartmentUpdate(BaseModel):
    """Request schema for updating a department."""

    name: str = Field(..., min_length=1, max_length=200)


class DepartmentResponse(BaseModel):
    """Response schema for a department."""

    id: int
    name: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
