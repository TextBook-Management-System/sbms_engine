"""Pydantic schemas for authentication endpoints."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserRegisterRequest(BaseModel):
    """Request schema for user registration."""

    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=1, max_length=200)
    id_number: Optional[str] = Field(None, max_length=50)
    gender: Optional[str] = Field(None, max_length=20)
    date_of_birth: Optional[str] = Field(None, description="Date of birth (YYYY-MM-DD)")
    role: Optional[str] = Field(None, description="Role to assign: DeptAdmin, SchoolAdmin, Teacher, Parent")
    department_id: Optional[int] = None
    school_id: Optional[int] = None


class UserLoginRequest(BaseModel):
    """Request schema for user login."""

    email: EmailStr
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    """Response schema for login/refresh token."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class AccessTokenResponse(BaseModel):
    """Response schema for refreshed access token."""

    access_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    """Request schema for token refresh."""

    refresh_token: str


class UserResponse(BaseModel):
    """Response schema for user profile (excludes password)."""

    id: int
    email: str
    full_name: str
    id_number: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[datetime] = None
    is_active: bool
    role: Optional[str] = None
    department_id: Optional[int] = None
    school_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# Rebuild TokenResponse to resolve the forward reference to UserResponse
TokenResponse.model_rebuild()
