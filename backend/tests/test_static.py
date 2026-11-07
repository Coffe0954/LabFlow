"""Сервер отдаёт собранный фронтенд (режим выкладки на Render)."""

from pathlib import Path

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.main import create_app


async def test_frontend_is_served_with_spa_fallback(
    tmp_path: Path, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>LabFlow</html>", encoding="utf-8")
    (tmp_path / "assets" / "app-123.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path.parent / "secret.txt").write_text("секрет", encoding="utf-8")

    app = create_app(session_factory, start_ticker=False, static_dir=str(tmp_path))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/")
        assert r.status_code == 200 and "LabFlow" in r.text

        r = await c.get("/teacher/queues/5")  # маршрут React Router
        assert r.status_code == 200 and "LabFlow" in r.text

        r = await c.get("/assets/app-123.js")
        assert r.text == "console.log(1)"
        assert "immutable" in r.headers["cache-control"]

        r = await c.get("/api/v1/unknown")  # API не подменяется страницей сайта
        assert r.status_code == 404
        assert r.json() == {"detail": "Не найдено"}

        assert (await c.get("/health")).json() == {"status": "ok"}
        assert (await c.get("/api/v1/ads/active")).status_code == 200

        r = await c.get("/../secret.txt")  # выйти за пределы папки нельзя
        assert "секрет" not in r.text


def test_database_url_from_hosting_uses_async_driver() -> None:
    from app.core.config import Settings

    url = "postgres://u:p@host:5432/db"
    assert Settings(database_url=url).database_url == "postgresql+asyncpg://u:p@host:5432/db"
    url = "postgresql://u:p@host/db"
    assert Settings(database_url=url).database_url == "postgresql+asyncpg://u:p@host/db"
