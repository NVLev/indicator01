from datetime import datetime, timezone, timedelta

from jose import JWTError, jwt

from ..core.config import settings
from ..services.auth_service import AuthService, pwd_context
from ..core.db_helper import db_helper
from ..core.models import User, RefreshToken
from ..core.schemas import Token, TokenResponse, UserCreate, UserRead, LoginRequest, RefreshTokenRequest
from ..services.security import get_current_user
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

router = APIRouter(prefix="/auth", tags=["Auth"])


from fastapi import APIRouter, Depends, HTTPException


@router.post("/register", response_model=UserRead)
async def register(
    user_data: UserCreate, session: AsyncSession = Depends(db_helper.session_getter)
):
    try:
        user = await AuthService.register(user_data, session)

        stmt = select(User).where(User.id == user.id)
        result = await session.execute(stmt)
        user = result.scalar_one()

        return {
            "id": user.id,
            "email": user.email,
            "is_active": user.is_active,
            "created_at": user.created_at,
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        import traceback

        print("Ошибка:", e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Ошибка сервера")


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: LoginRequest, session: AsyncSession = Depends(db_helper.session_getter)
):
    auth_result = await AuthService.authenticate(credentials.email, credentials.password, session)
    # user = await AuthService.authenticate(credentials.email, credentials.password, session)
    #
    # refresh_token, jti, iat, exp = AuthService.create_refresh_token(user["user_id"])


    return {
        "access_token": auth_result["access_token"],
        "refresh_token": auth_result["refresh_token"],
        "token_type": "bearer",
    }

@router.post("/refresh", response_model=Token)
async def refresh(
    refresh_token: str, session: AsyncSession = Depends(db_helper.session_getter)
):
    user_id = await AuthService.verify_refresh_token(refresh_token, session)
    if not user_id:
        raise HTTPException(
            status_code=401, detail="Неверный или просроченный refresh токен"
        )

    new_access = AuthService.create_access_token({"sub": str(user_id)})
    new_refresh = AuthService.create_refresh_token(user_id)

    hashed_refresh = pwd_context.hash(new_refresh)
    db_refresh_token = RefreshToken(
        user_id=user_id,
        token_hash=hashed_refresh,
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=settings.auth.REFRESH_EXPIRE_DAYS),
        revoked=False,
    )
    session.add(db_refresh_token)
    await session.commit()

    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
    }


@router.post("/logout")
async def logout(
    token_data: RefreshTokenRequest, session: AsyncSession = Depends(db_helper.session_getter)
):
    refresh_token = token_data.refresh_token
    try:
        payload = jwt.decode(
            refresh_token,
            settings.auth.secret_key,
            algorithms=[settings.auth.algorithm]
        )
        user_id = int(payload.get("sub"))
        if payload.get("type") != "refresh":
            raise ValueError()
    except (JWTError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    stmt = select(RefreshToken).where(
        RefreshToken.user_id == user_id,
        RefreshToken.revoked == False)
    result = await session.execute(stmt)
    tokens = result.scalars().all()
    for token in tokens:
        if pwd_context.verify(refresh_token, token.token_hash):
            print(">>> logout matched token:", token.id)
            print(">>> decoded user_id =", user_id, "total tokens:", len(tokens))
            token.revoked = True
            await session.commit()
            return {"message": "Выход выполнен"}
    raise HTTPException(status_code=400, detail="Токен не найден")


@router.get("/me", response_model=UserRead)
async def get_me(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(db_helper.session_getter),
):
    stmt = (
        select(User)
        .where(User.id == current_user.id)
    )
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user

