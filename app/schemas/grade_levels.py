"""Pydantic schemas for grade levels endpoints."""

from pydantic import BaseModel, Field


class GradeLevelCreate(BaseModel):
    """Request schema for creating a grade level."""

    name: str = Field(..., min_length=1, max_length=100)


class GradeLevelUpdate(BaseModel):
    """Request schema for updating a grade level."""

    name: str = Field(..., min_length=1, max_length=100)


class GradeLevelResponse(BaseModel):
    """Response schema for a grade level."""

    id: int
    name: str

    model_config = {"from_attributes": True}
