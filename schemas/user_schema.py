from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field

from models.user_model import UserRole


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=120)
    flat_number: Optional[str] = None
    phone: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str

class RoleChangeRequestCreate(BaseModel):
    requested_role: UserRole

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    name: str
    role: UserRole
    flat_number: Optional[str]
    phone: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserProfileUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    flat_number: Optional[str] = None
    phone: Optional[str] = None


class UserListResponse(BaseModel):
    total: int
    items: list[UserResponse]