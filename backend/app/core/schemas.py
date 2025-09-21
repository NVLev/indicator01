import json
from enum import Enum
from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import datetime
from typing import List, Optional, Dict, Any, Union



class UserBase(BaseModel):
    email: EmailStr = Field(..., description="Email пользователя")


class UserCreate(UserBase):
    password: str = Field(..., description="Пароль (минимум 6 символов)", min_length=6)


class UserUpdate(UserBase):
    email: Optional[EmailStr] = Field(None, description="Новый email")
    password: Optional[str] = Field(
        None, min_length=6, description="Новый пароль (минимум 6 символов)"
    )
    is_active: Optional[bool] = Field(None, description="Активность аккаунта")


class UserRead(UserBase):
    """
    Схема для чтения данных пользователя
    """

    id: int = Field(..., description="Уникальный идентификатор пользователя")
    email: EmailStr = Field(..., description="Email пользователя")
    is_active: bool = Field(..., description="Активен ли аккаунт")
    created_at: datetime = Field(..., description="Дата и время создания аккаунта")

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    email: str
    password: str


class Token(BaseModel):
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Тип токена")
    refresh_token: Optional[str] = Field(None, description="Refresh token")


class TokenPayload(BaseModel):
    sub: Optional[int] = None
    exp: Optional[int] = None


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="Refresh token")
    token_type: str = Field(default="bearer", description="Тип токена")

class RefreshTokenRequest(BaseModel):
    refresh_token: str
