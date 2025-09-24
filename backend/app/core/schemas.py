import json
from enum import Enum
from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict
from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from enum import Enum
from .models import StudyStatus



# Модели для авторизации

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


# Схемы для обработки исследований

class StudyBase(BaseModel):
    """Базовая схема исследований"""
    filename: str


class StudyCreate(StudyBase):
    """Схема для создания нового исследования"""
    pass


class StudyUpdate(BaseModel):
    """Схема для обновления результатов обработки исследования"""
    study_uid: Optional[str] = None
    series_uid: Optional[str] = None
    processing_status: Optional[StudyStatus] = None
    probability_of_pathology: Optional[float] = None
    pathology: Optional[int] = None
    time_of_processing: Optional[float] = None
    most_dangerous_pathology_type: Optional[str] = None
    pathology_localization_coords: Optional[Dict[str, float]] = None
    heatmap_path: Optional[str] = None
    heatmap_format: Optional[str] = None
    heatmap_metadata: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

# Дополнительная схема для координат локализации
class PathologyLocalization(BaseModel):
    """Схема для координат локализации патологии"""
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    z_min: float
    z_max: float
    confidence: Optional[float] = None

class StudyResponse(StudyBase):
    """Схема для ответа"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    file_path: str
    path_to_study: Optional[str] = None
    study_uid: Optional[str] = None
    series_uid: Optional[str] = None
    processing_status: str
    probability_of_pathology: Optional[float] = None
    pathology: Optional[int] = None
    time_of_processing: Optional[float] = None
    most_dangerous_pathology_type: Optional[str] = None
    pathology_localization_coords: Optional[PathologyLocalization] = None
    heatmap_path: Optional[str] = None
    heatmap_format: Optional[str] = None
    heatmap_metadata: Optional[Dict[str, Any]] = None
    total_instances: Optional[int] = None
    series_count: Optional[int] = None
    error_message: Optional[str] = None
    ready_for_inference: bool
    inference_completed: bool
    created_at: datetime
    updated_at: datetime
    needs_review: bool = Field(False, description="Требуется проверка врачом")
    verification_score: Optional[float] = Field(None, description="Оценка достоверности AI")
    verification_warnings: List[str] = Field([], description="Предупреждения верификации")

    @field_validator('processing_status', mode='before')
    @classmethod
    def validate_processing_status(cls, v):
        """Преобразуем статусы в русскоязычные для ответа"""
        status_mapping = {
            'uploaded': 'загружено',
            'extracting': 'распаковывается',
            'validating': 'проверяется',
            'processing_ml': 'анализируется_ИИ',
            'completed': 'обработано',
            'failed': 'ошибка',
            'needs_review': 'требует_проверки',
            # Английские версии на всякий случай
            'UPLOADED': 'загружено',
            'EXTRACTING': 'распаковывается',
            'VALIDATING': 'проверяется',
            'PROCESSING_ML': 'анализируется_ИИ',
            'COMPLETED': 'обработано',
            'FAILED': 'ошибка',
            'NEEDS_REVIEW': 'требует_проверки'
        }

        if isinstance(v, StudyStatus):
            return v.value
        elif isinstance(v, str):
            return status_mapping.get(v.lower(), v)
        return v

    @field_validator('created_at', 'updated_at', mode='before')
    @classmethod
    def validate_datetime(cls, v):
        """Преобразуем datetime объекты в строки для сериализации"""
        if v is None:
            return None
        return v.isoformat() if hasattr(v, 'isoformat') else v


class StudyListResponse(BaseModel):
    """Схема для списка исследований с пагинацией"""
    studies: List[StudyResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class StudyStatusResponse(BaseModel):
    """Простой ответ по статусу"""
    id: int
    processing_status: StudyStatus
    progress: Optional[float] = None
    error_message: Optional[str] = None


class ExcelReportRequest(BaseModel):
    """Схема генерации отчета в Excel"""
    study_ids: List[int]
    include_metadata: bool = True


# Дополнительная схема для координат локализации
class PathologyLocalization(BaseModel):
    """Схема для координат локализации патологии"""
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    z_min: float
    z_max: float
    confidence: Optional[float] = None




