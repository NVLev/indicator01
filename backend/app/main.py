import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager

from .routes import auth
from .core.db_helper import db_helper


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Управление жизненным циклом приложения:
    - Инициализация при старте
    - Корректное завершение при остановке
    """

    print("Приложение запущено. Подключение к базе данных готово.")
    try:
        yield  # Передаём управление приложению
    finally:
        await db_helper.dispose()
        print("Соединение с базой данных закрыто.")


app = FastAPI(lifespan=lifespan)


app.include_router(auth.router)