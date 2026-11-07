# Один образ для Render: собранный сайт + сервер FastAPI (сайт, API и WebSocket на одном адресе).

# --- 1. Сборка фронтенда ---
FROM node:24-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --- 2. Сервер ---
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ENVIRONMENT=production \
    STATIC_DIR=/app/static
WORKDIR /app
COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install .
COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY backend/start.sh ./start.sh
COPY --from=frontend /build/dist ./static
RUN chmod +x start.sh && useradd --create-home labflow
USER labflow
EXPOSE 8000
CMD ["./start.sh"]
