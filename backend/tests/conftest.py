"""Общие фикстуры.

По умолчанию тесты идут на SQLite в памяти. В CI задаётся TEST_DATABASE_URL
с PostgreSQL — тогда те же тесты проверяют реальную БД.
"""

import os
from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.security import hash_password
from app.db.base import Base
from app.main import create_app
from app.models import User, UserRole

TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "sqlite+aiosqlite://")


@pytest.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    if TEST_DB_URL.startswith("sqlite"):
        engine = create_async_engine(
            TEST_DB_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
    else:
        engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def client(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncClient]:
    app = create_app(session_factory, start_ticker=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as c:
        yield c


class Api:
    """Помощник: создаёт пользователей и делает запросы от их имени."""

    def __init__(self, client: AsyncClient, factory: async_sessionmaker[AsyncSession]) -> None:
        self.client = client
        self.factory = factory
        self._n = 0

    async def user(self, role: UserRole, name: str = "") -> dict[str, str]:
        """Создаёт пользователя с ролью и возвращает заголовки авторизации."""
        self._n += 1
        email = f"{role}{self._n}@test.ru"
        async with self.factory() as db:
            db.add(
                User(
                    email=email,
                    password_hash=hash_password("secret123"),
                    full_name=name or f"{role.title()} {self._n}",
                    group="М8О-312БВ-24",
                    role=role,
                )
            )
            await db.commit()
        r = await self.client.post("/auth/login", json={"email": email, "password": "secret123"})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    async def ok(self, method: str, url: str, headers: dict[str, str], **kw: Any) -> Any:
        r = await self.client.request(method, url, headers=headers, **kw)
        assert r.status_code < 300, f"{method} {url}: {r.status_code} {r.text}"
        return r.json() if r.content else None


@pytest.fixture
def api(client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]) -> Api:
    return Api(client, session_factory)
