import os
import sys
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from .config import settings


class DatabaseHelper:
    """
    Вспомогательный класс для управления подключениями к базе данных и сессиями.
    Атрибуты:
        engine (AsyncEngine): Асинхронный движок SQLAlchemy
        session_factory (async_sessionmaker): Фабрика для создания асинхронных сессий
    """

    def __init__(
        self,
        url: str,
        echo: bool = False,
        echo_pool: bool = False,
        pool_size: int = 5,
        max_overflow: int = 10,
    ) -> None:
        self.engine: AsyncEngine = create_async_engine(
            url=url,
            echo=echo,
            echo_pool=echo_pool,
            pool_size=pool_size,
            max_overflow=max_overflow,
        )
        self.session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )

    async def dispose(self) -> None:
        """
        Закрывает все соединения
        """
        await self.engine.dispose()
        print("dispose engine")

    async def session_getter(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Асинхронный генератор для получения сессии базы данных.
        Сессия автоматически закрывается при выходе из контекста.
        Yields:
            AsyncSession: Сессия базы данных
        """
        session = self.session_factory()
        async with session:
            yield session


db_helper = DatabaseHelper(
    url=settings.db.url,
    echo=settings.db.echo,
    echo_pool=settings.db.echo_pool,
    pool_size=settings.db.pool_size,
    max_overflow=settings.db.max_overflow,
)
