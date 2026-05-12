"""Pydantic schemas for learners endpoints."""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class LearnerCreate(BaseModel):
    """Request schema for creating a learner."""

    grade_id: int
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    id_number: Optional[str] = Field(None, max_length=50)
    gender: Optional[str] = Field(None, max_length=20)
    date_of_birth: Optional[date] = None
    parent_id: Optional[int] = Field(None, description="Optional parent user ID to link on creation")


class LearnerUpdate(BaseModel):
    """Request schema for updating a learner."""

    grade_id: Optional[int] = None
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    id_number: Optional[str] = Field(None, max_length=50)
    gender: Optional[str] = Field(None, max_length=20)
    date_of_birth: Optional[date] = None


class LearnerResponse(BaseModel):
    """Response schema for a learner."""

    id: int
    grade_id: int
    first_name: str
    last_name: str
    id_number: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ParentLearnerCreate(BaseModel):
    """Request schema for linking a parent to a learner."""

    user_id: int


class ParentLearnerResponse(BaseModel):
    """Response schema for a parent-learner link."""

    id: int
    parent_id: int
    learner_id: int

    model_config = {"from_attributes": True}
