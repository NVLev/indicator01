from typing import Optional, List, Dict, Any
from xmlrpc.client import boolean
from datetime import timedelta
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

Base = declarative_base()

class User(Base):
    """
    Модель пользователя  с email и хешированным паролем
    Атрибуты:
        id (int): Уникальный идентификатор
        email (str): Уникальный email
        hashed_password (str): Хешированный пароль
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    pass_hash: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )

class RefreshToken(Base):
    """
    Модель для хранения токенов
    Атрибуты:
        user_id (int): Уникальный идентификатор
        role_id:
    """

    __tablename__ = "refresh_tokens"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    jti: Mapped[str] = mapped_column(String(36), unique=True, index=True)  # UUID токена
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    issued_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), default=lambda: func.now() + timedelta(days=7)
    )
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")
