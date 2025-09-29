from typing import Optional, List, Dict, Any
from xmlrpc.client import boolean
from datetime import timedelta
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Boolean, Float, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from enum import Enum

Base = declarative_base()

class StudyStatus(str, Enum):
    """Статусы обработки исследования на русском языке"""
    UPLOADED = "загружено"
    EXTRACTING = "распаковывается"
    VALIDATING = "проверяется"
    PROCESSING_ML = "анализируется_ИИ"
    COMPLETED = "обработано"
    FAILED = "ошибка"
    NEEDS_REVIEW = "требует_проверки"

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
    studies: Mapped[list["Study"]] = relationship(
        "Study",
        back_populates="user",
        cascade="all, delete-orphan"
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


class Study(Base):
    """Модель исследований для отслеживания обработки DICOM"""
    __tablename__ = "studies"

    id: Mapped[int] = mapped_column(primary_key=True)


    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)  # ID задачи Celery
    # Необходимые поля, согласно спецификации
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    path_to_study: Mapped[Optional[str]] = mapped_column(String(500))  # Путь к исследованию
    study_uid: Mapped[Optional[str]] = mapped_column(String(255), index=True)  # Из тэгов DICOM
    series_uid: Mapped[Optional[str]] = mapped_column(String(255))  # Из тэгов DICOM

    #  Результаты обработки
    processing_status: Mapped[StudyStatus] = mapped_column(
        String(50),
        nullable=False,
        default=StudyStatus.UPLOADED,
        index=True
    )
    
    probability_of_pathology: Mapped[Optional[float]] = mapped_column(Float, default=0.0)  # от 0.0 до 1.0
    pathology: Mapped[Optional[int]] = mapped_column(Integer, default=0)  # 0 = normal, 1 = pathology
    time_of_processing: Mapped[Optional[float]] = mapped_column(Float)  # секунды

    #  Дополнительные поля
    most_dangerous_pathology_type: Mapped[Optional[str]] = mapped_column(String(255))
    pathology_localization_coords: Mapped[Optional[dict]] = mapped_column(JSON)  # {x_min: 10, x_max: 20, ...}

    # Heatmap.  Пока непонятно, в каком виде, поэтому делется на все файлы)
    heatmap_path: Mapped[Optional[str]] = mapped_column(String(500))
    heatmap_format: Mapped[Optional[str]] = mapped_column(String(20))
    heatmap_metadata: Mapped[Optional[dict]] = mapped_column(JSON)

    # Доп. метадата
    total_instances: Mapped[Optional[int]] = mapped_column(Integer)  # Количество файлов DICOM
    series_count: Mapped[Optional[int]] = mapped_column(Integer)  # Количество серий
    error_message: Mapped[Optional[str]] = mapped_column(Text)  # Ошибки
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON)

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # статусы обработки ML
    ready_for_inference: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    inference_completed: Mapped[bool] = mapped_column(Boolean, default=False)

    # Поля для верификации
    needs_verification: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verification_results: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    verification_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="studies")




