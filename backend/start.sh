#!/bin/sh
# Запуск в контейнере: миграции → демо-данные (если включены) → сервер.
set -e
alembic upgrade head
if [ "${SEED_DEMO:-false}" = "true" ]; then
  python -m app.seed
fi
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" \
  --proxy-headers --forwarded-allow-ips='*'
