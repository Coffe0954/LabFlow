"""Точка входа FastAPI. Запуск: uvicorn app.main:app --reload"""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api import ads, auth, entries, labs, queues, stats, tests
from app.core.config import settings
from app.db.session import SessionLocal
from app.services import queue_service as qs
from app.ws import routes as ws_routes
from app.ws.hub import hub

logger = logging.getLogger("labflow")

API_PREFIX = "/api/v1"


async def queue_ticker(factory: async_sessionmaker[AsyncSession], interval: float) -> None:
    """Раз в минуту пересчитывает очереди с подписчиками: с ростом W меняется key (aging)."""
    while True:
        await asyncio.sleep(interval)
        for queue_id in hub.active_queue_ids():
            try:
                async with factory() as db:
                    await qs.publish(db, queue_id)
            except Exception:
                logger.exception("Не удалось пересчитать очередь %s", queue_id)


def _validation_message(exc: RequestValidationError) -> str:
    parts = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err.get("loc", ()) if p not in ("body", "query", "path"))
        msg = str(err.get("msg", "")).removeprefix("Value error, ")
        parts.append(f"{loc}: {msg}" if loc else msg)
    return "; ".join(parts) or "Некорректные данные"


def create_app(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    start_ticker: bool = True,
    static_dir: str | None = settings.static_dir,
) -> FastAPI:
    settings.check_production()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        task = None
        if start_ticker:
            task = asyncio.create_task(
                queue_ticker(app.state.session_factory, settings.queue_tick_seconds)
            )
        yield
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    app = FastAPI(
        title="LabFlow API",
        description="Умная очередь на сдачу лабораторных",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        openapi_url=f"{API_PREFIX}/openapi.json",
    )
    app.state.session_factory = session_factory or SessionLocal

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Единый формат ошибок: {"detail": "текст"}.
    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": _validation_message(exc)},
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Необработанная ошибка", exc_info=exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Внутренняя ошибка сервера"},
        )

    for module in (auth, queues, entries, labs, tests, stats, ads):
        app.include_router(module.router, prefix=API_PREFIX)
    app.include_router(ws_routes.router, prefix=API_PREFIX)

    @app.get("/health", tags=["service"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    if static_dir is not None:
        mount_frontend(app, Path(static_dir))
    return app


def mount_frontend(app: FastAPI, root: Path) -> None:
    """Отдаёт собранный фронтенд: файлы как есть, остальные пути — index.html (SPA).

    Регистрируется последним, поэтому /api, /docs и /health не перехватывает.
    """
    root = root.resolve()
    index = root / "index.html"
    if not index.is_file():
        raise RuntimeError(f"Не найден собранный фронтенд: {index}")

    @app.get("/{path:path}", include_in_schema=False)
    async def frontend(path: str) -> Response:
        if path.startswith("api/"):
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND, content={"detail": "Не найдено"}
            )
        file = (root / path).resolve()
        # Защита от выхода за пределы папки (../../etc/passwd).
        if path and file.is_file() and file.is_relative_to(root):
            # Файлы сборки с хэшем в имени можно кэшировать надолго.
            cache = (
                "public, max-age=31536000, immutable" if path.startswith("assets/") else "no-cache"
            )
            return FileResponse(file, headers={"Cache-Control": cache})
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


app = create_app()
