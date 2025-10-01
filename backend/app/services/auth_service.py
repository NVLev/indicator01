from datetime import datetime, timedelta, timezone
from typing import Any, Coroutine, Optional
from uuid import uuid4

from fastapi import Depends, HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from ..core.config import settings
from ..core.db_helper import db_helper
from ..core.models import RefreshToken, User
from ..core.schemas import UserCreate

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """
    Сервис для обработки операций аутентификации.
    Включает хеширование паролей, верификацию, создание JWT-токенов,
    регистрацию и аутентификацию пользователей.
    """

    @staticmethod
    def get_password_hash(password: str) -> str:
        """
        Генерация безопасного хеша для пароля.
        :param password: Пароль в открытом виде
        :return: str: Хешированный пароль
        """
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        Проверка пароля.
        :param plain_password: Пароль для проверки
        :param hashed_password: Хранимый хеш пароля
        :return:  bool: True если пароли совпадают, иначе False
        """
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
        """
        Создание JWT-токена доступа.
        :param data: Данные для включения в токен
        :param expires_delta:
        :return: str: Закодированный JWT-токен
        """
        to_encode = data.copy()
        expire = datetime.now(tz=timezone.utc) + (
            expires_delta or timedelta(minutes=settings.auth.ACCESS_EXPIRE_MINUTES)
        )
        to_encode.update({"exp": int(expire.timestamp())})
        return jwt.encode(
            to_encode,
            settings.auth.secret_key,
            algorithm=settings.auth.algorithm,
        )

    @staticmethod
    def create_refresh_token(user_id: int) -> tuple[str, str, datetime, datetime]:
        """
        Создает обновленный JWT-токен jti, iat, exp.
        Возвращает сам токен (JWT), jti, issued_at, expires_at.
        """
        jti = str(uuid4())
        issued_at = datetime.now(timezone.utc)
        expires_at = issued_at + timedelta(days=settings.auth.REFRESH_EXPIRE_DAYS)

        payload = {
            "sub": str(user_id),
            "type": "refresh",
            "jti": jti,
            "iat": int(issued_at.timestamp()),
            "exp": int(expires_at.timestamp()),
        }
        secret_key = settings.auth.secret_key
        if isinstance(secret_key, tuple):
            secret_key = secret_key[0]
        token = jwt.encode(
            payload,
            settings.auth.secret_key,
            algorithm=settings.auth.algorithm,
        )

        return token, jti, issued_at, expires_at

    @classmethod
    async def persist_refresh_token(
        cls,
        user_id: int,
        refresh_token: str,
        jti: str,
        issued_at: datetime,
        expires_at: datetime,
        session: AsyncSession,
    ):
        """
        Сохраняет refresh-токен в БД.
        По желанию можно отзывать старые токены (rotation).
        """
        # Отозвать старые токены
        stmt = select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked == False,
        )
        result = await session.execute(stmt)
        for token in result.scalars().all():
            token.revoked = True

        # Хранение хэш JWT-токена
        hashed = pwd_context.hash(refresh_token)

        db_token = RefreshToken(
            user_id=user_id,
            jti=jti,
            token_hash=hashed,
            issued_at=issued_at,
            expires_at=expires_at,
            revoked=False,
        )
        session.add(db_token)
        await session.commit()

    @classmethod
    async def register(
        cls,
        user_data: UserCreate,
        session: AsyncSession = Depends(db_helper.session_getter),
    ) -> User:
        """
        Регистрация нового пользователя.
        """
        if not user_data.email or not user_data.password:
            raise HTTPException(status_code=400, detail="Email и пароль обязательны")

        # Упрощенная проверка существования пользователя
        existing_user = await session.execute(
            select(User).where(User.email == user_data.email)
        )
        if existing_user.scalar_one_or_none():
            raise HTTPException(
                status_code=400, detail="Пользователь с таким email уже существует"
            )

        user = User(
            email=user_data.email,
            pass_hash=cls.get_password_hash(user_data.password),
            is_active=True,
        )

        session.add(user)
        try:
            await session.commit()
            await session.refresh(user)
            return user
        except Exception as e:
            await session.rollback()
            raise HTTPException(
                status_code=500, detail=f"Ошибка при создании пользователя: {str(e)}"
            )

    @classmethod
    async def authenticate(
        cls, email: str, password: str, session: AsyncSession
    ) -> dict[str, Any]:
        """
        Аутентификация пользователя и генерация токена доступа.
        :param email: email: Email пользователя
        :param password: password: Пароль пользователя
        :param session: session: Сессия базы данных
        :return: str: JWT-токен доступа
        """
        if not email or not password:
            raise HTTPException(status_code=400, detail="Email и пароль обязательны")
        stmt = (
            select(User)
            .where(User.email == email)
            .options(selectinload(User.refresh_tokens))
            .execution_options(populate_existing=True)
        )
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if not user or not cls.verify_password(password, user.pass_hash):
            raise HTTPException(status_code=401, detail="Неверный email или пароль")

        if not user.is_active:
            raise HTTPException(status_code=403, detail="Аккаунт деактивирован")
        access_token = cls.create_access_token({"sub": str(user.id)})
        refresh_token, jti, issued_at, expires_at = cls.create_refresh_token(user.id)

        await cls.persist_refresh_token(
            user.id, refresh_token, jti, issued_at, expires_at, session
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user_id": user.id,
        }

    @classmethod
    async def verify_refresh_token(
        cls, refresh_token: str, session: AsyncSession
    ) -> Optional[int]:
        """
        Проверяет refresh-токен и возвращает user_id, если он валиден.
        """
        try:
            payload = jwt.decode(
                refresh_token,
                settings.auth.secret_key,
                algorithms=[settings.auth.algorithm],
            )
            if payload.get("type") != "refresh":
                return None

            user_id = int(payload.get("sub"))
            jti = payload.get("jti")
            if not jti:
                return None
        except (JWTError, ValueError):
            return None

        # Поиск токена по jti
        stmt = select(RefreshToken).where(
            RefreshToken.jti == jti,
            RefreshToken.user_id == user_id,
            RefreshToken.revoked == False,
            RefreshToken.expires_at > datetime.now(timezone.utc),
        )
        result = await session.execute(stmt)
        db_token = result.scalar_one_or_none()

        if not db_token:
            return None

        # Проверка хэша
        if not pwd_context.verify(refresh_token, db_token.token_hash):
            return None

        return user_id
