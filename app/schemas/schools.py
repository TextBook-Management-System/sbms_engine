"""Pydantic schemas for schools endpoints."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SchoolCreate(BaseModel):
    """Request schema for creating a school."""

    department_id: int
    name: str = Field(..., min_length=1, max_length=200)
    address: str = Field(..., min_length=1, max_length=500)
    city: str = Field(..., min_length=1, max_length=100)
    state: str = Field(..., min_length=1, max_length=100)
    country: str = Field(..., min_length=1, max_length=100)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    contact_person: Optional[str] = Field(None, max_length=200)
    phone_number: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=255)
    total_students: int = Field(0, ge=0)
    total_teachers: int = Field(0, ge=0)


class SchoolUpdate(BaseModel):
    """Request schema for updating a school."""

    department_id: Optional[int] = None
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    address: Optional[str] = Field(None, min_length=1, max_length=500)
    city: Optional[str] = Field(None, min_length=1, max_length=100)
    state: Optional[str] = Field(None, min_length=1, max_length=100)
    country: Optional[str] = Field(None, min_length=1, max_length=100)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    contact_person: Optional[str] = Field(None, max_length=200)
    phone_number: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=255)
    total_students: Optional[int] = Field(None, ge=0)
    total_teachers: Optional[int] = Field(None, ge=0)


class SchoolResponse(BaseModel):
    """Response schema for a school."""

    id: int
    department_id: int
    name: str
    address: str
    city: str
    state: str
    country: str
    latitude: float
    longitude: float
    contact_person: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    total_students: int
    total_teachers: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
