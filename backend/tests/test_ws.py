"""Настоящий WebSocket-эндпоинт: авторизация, первое состояние, обновление после записи."""

import asyncio
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.security import hash_password
from app.db.base import Base
from app.main import create_app
from app.models import Discipline, Lab, User, UserRole


def test_websocket_stream(tmp_path: Path) -> None:
    # Отдельная файловая SQLite: TestClient работает в своём event loop.
    url = f"sqlite+aiosqlite:///{tmp_path / 'ws.db'}"

    async def prepare() -> None:
        engine = create_async_engine(url, poolclass=NullPool)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as db:
            pw = hash_password("secret123")
            db.add_all(
                [
                    User(
                        email="t@t.ru", password_hash=pw, full_name="Препод", role=UserRole.teacher
                    ),
                    User(
                        email="s@t.ru", password_hash=pw, full_name="Студент", role=UserRole.student
                    ),
                    Discipline(title="ООП", labs=[Lab(number=1, title="ЛР1", expected_minutes=15)]),
                ]
            )
            await db.commit()
        await engine.dispose()

    asyncio.run(prepare())
    engine = create_async_engine(url, poolclass=NullPool)
    app = create_app(async_sessionmaker(engine, expire_on_commit=False), start_ticker=False)

    with TestClient(app) as client:

        def login(email: str) -> str:
            r = client.post("/api/v1/auth/login", json={"email": email, "password": "secret123"})
            return str(r.json()["access_token"])

        teacher, student = login("t@t.ru"), login("s@t.ru")
        r = client.post(
            "/api/v1/queues",
            headers={"Authorization": f"Bearer {teacher}"},
            json={
                "discipline_id": 1,
                "date": "2026-11-07",
                "starts_at": "09:00",
                "ends_at": "10:30",
            },
        )
        qid = r.json()["id"]

        with (
            pytest.raises(WebSocketDisconnect),
            client.websocket_connect(f"/api/v1/ws/queues/{qid}?token=bad") as ws,
        ):
            ws.receive_json()

        with client.websocket_connect(f"/api/v1/ws/queues/{qid}?token={student}") as ws:
            first = ws.receive_json()
            assert first["type"] == "queue_state"
            assert first["data"]["waiting"] == []

            ws.send_text("ping")
            assert ws.receive_text() == "pong"

            client.post(
                f"/api/v1/queues/{qid}/entries",
                headers={"Authorization": f"Bearer {student}"},
                json={"lab_ids": [1]},
            )
            update = ws.receive_json()
            assert [e["student_name"] for e in update["data"]["waiting"]] == ["Студент"]
            assert update["data"]["waiting"][0]["position"] == 1
