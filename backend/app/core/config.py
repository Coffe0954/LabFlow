"""Настройки приложения. Все секреты берутся из переменных окружения (или файла .env)."""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET = "dev-secret-change-me-in-production-please"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"  # development | production
    database_url: str = "postgresql+asyncpg://labflow:labflow@localhost:5432/labflow"
    secret_key: str = DEV_SECRET
    access_token_expire_minutes: int = 60 * 12
    cors_origins: list[str] = ["http://localhost:5173"]
    # Как часто пересчитывать очереди по таймеру (aging меняет порядок со временем).
    queue_tick_seconds: int = 60
    # Папка с собранным фронтендом. Если задана — сервер сам отдаёт сайт (один адрес
    # для сайта, API и WebSocket, CORS не нужен). Так устроена выкладка на Render.
    static_dir: str | None = None

    @field_validator("database_url")
    @classmethod
    def _async_driver(cls, url: str) -> str:
        """Хостинги дают адрес вида postgres://… — переводим на асинхронный драйвер."""
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+asyncpg://" + url[len(prefix) :]
        return url

    def check_production(self) -> None:
        """В проде запрещаем запуск с секретом по умолчанию."""
        if self.environment == "production" and self.secret_key == DEV_SECRET:
            raise RuntimeError("Задайте SECRET_KEY в переменных окружения")


settings = Settings()
