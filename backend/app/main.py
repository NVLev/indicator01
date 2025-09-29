import os
import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from .routes import auth, studies, demo
from .core.db_helper import db_helper


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Управление жизненным циклом приложения:
    - Инициализация при старте
    - Создание демо-пользователя
    - Корректное завершение при остановке
    """

    print("🚀 Приложение запущено. Подключение к базе данных готово.")

    try:
        # Создаем демо-пользователя при старте
        await create_demo_user()
        print("✅ Демо-режим готов к работе")

        yield

    finally:
        await db_helper.dispose()
        print("🔴 Соединение с базой данных закрыто.")


# ----------БЛОК ДЛЯ ДЕМО------------
async def create_demo_user():
    """Создает демо-пользователя и получает токены при запуске"""
    try:
        from app.core.models import User
        from app.services.auth_service import AuthService  # ✅ ПРАВИЛЬНЫЙ ИМПОРТ
        from sqlalchemy import select

        # ✅ ПРАВИЛЬНОЕ ИСПОЛЬЗОВАНИЕ session_getter
        async for session in db_helper.session_getter():
            # Проверяем/создаем пользователя
            stmt = select(User).where(User.email == "demo@test.com")
            result = await session.execute(stmt)
            existing_user = result.scalar_one_or_none()

            if not existing_user:
                # ✅ ИСПОЛЬЗУЕМ AuthService.get_password_hash
                password_hash = AuthService.get_password_hash("demo_password_123")

                # Создаем пользователя
                demo_user = User(
                    email="demo@test.com",
                    pass_hash=password_hash,
                    is_active=True
                )
                session.add(demo_user)
                await session.commit()
                await session.refresh(demo_user)
                print(f"✅ Создан демо-пользователь: {demo_user.email} (ID: {demo_user.id})")
            else:
                demo_user = existing_user
                print(f"✅ Демо-пользователь уже существует: {demo_user.email} (ID: {demo_user.id})")

            # ✅ ПОЛУЧАЕМ JWT ТОКЕНЫ через AuthService
            auth_result = await AuthService.authenticate(
                email="demo@test.com",
                password="demo_password_123",
                session=session
            )

            # ✅ СОХРАНЯЕМ В DemoService
            from app.services.demo_service import DemoService
            DemoService.set_demo_data(demo_user, auth_result)

            print(f"✅ Получены JWT токены для демо-режима")
            if auth_result and 'access_token' in auth_result:
                print(f"   Access Token: {auth_result['access_token'][:50]}...")
            else:
                print("   ⚠️ Токены не получены")

            break  # Важно: break после использования сессии

    except Exception as e:
        print(f"⚠️ Не удалось создать демо-пользователя/токены: {e}")
        import traceback
        traceback.print_exc()

# ---------------КОНЕЦ БЛОКА-------------------------


app = FastAPI(lifespan=lifespan)

# Абсолютные пути
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # /app/backend/app
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

print(f"🔍 BASE_DIR: {BASE_DIR}")
print(f"🔍 TEMPLATES_DIR: {TEMPLATES_DIR}")
print(f"🔍 STATIC_DIR: {STATIC_DIR}")
print(f"🔍 Templates exists: {os.path.exists(TEMPLATES_DIR)}")
print(f"🔍 Static exists: {os.path.exists(STATIC_DIR)}")

if os.path.exists(TEMPLATES_DIR):
    print(f"📁 Files in templates: {os.listdir(TEMPLATES_DIR)}")

# ПРАВИЛЬНАЯ настройка шаблонов - используем абсолютный путь
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Настройка статических файлов
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.include_router(auth.router)
app.include_router(studies.router)
app.include_router(demo.router)  # для демо, пока нет фронта