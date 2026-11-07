"""Подключение к БД и выдача сессий."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.requests import HTTPConnection

from app.core.config import settings

engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db(conn: HTTPConnection) -> AsyncIterator[AsyncSession]:
    """Сессия на один запрос. Фабрика берётся из app.state, чтобы тесты могли её подменить."""
    factory: async_sessionmaker[AsyncSession] = conn.app.state.session_factory
    async with factory() as session:
        yield session
