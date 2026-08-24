from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    is_admin: bool
    created_at: datetime

    class Config:
        from_attributes = True


class PreferencesUpdate(BaseModel):
    preferred_styles: list[str] = []
    preferred_colors: list[str] = []
    preferred_categories: list[str] = []
    budget_min: float = 0
    budget_max: float = 10000


class PreferencesResponse(PreferencesUpdate):
    class Config:
        from_attributes = True


TokenResponse.model_rebuild()
