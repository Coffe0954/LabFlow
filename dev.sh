#!/usr/bin/env bash
# Запуск LabFlow для разработки одной командой: ./dev.sh
# Поднимает backend (порт 8000) и frontend (порт 5173). Ctrl+C останавливает оба.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
FRONT_PORT="${FRONT_PORT:-5173}"  # другой порт: FRONT_PORT=5174 ./dev.sh

# Первый запуск: ставим зависимости, если их ещё нет.
if [ ! -x "$BACKEND/.venv/bin/uvicorn" ]; then
  echo "→ Устанавливаю зависимости backend…"
  python3 -m venv "$BACKEND/.venv"
  "$BACKEND/.venv/bin/pip" install -q -e "$BACKEND[dev]"
fi
if [ ! -f "$BACKEND/.env" ]; then
  cp "$BACKEND/.env.example" "$BACKEND/.env"
fi
if [ ! -d "$FRONTEND/node_modules" ]; then
  echo "→ Устанавливаю зависимости frontend…"
  (cd "$FRONTEND" && npm install --silent)
fi

for port in 8000 "$FRONT_PORT"; do
  if ss -ltn 2>/dev/null | grep -q ":$port "; then
    echo "✗ Порт $port уже занят — видимо, сервер уже запущен в другом терминале."
    echo "  Остановите его (Ctrl+C) и запустите ./dev.sh снова."
    exit 1
  fi
done

echo "→ Применяю миграции БД…"
(cd "$BACKEND" && .venv/bin/alembic upgrade head)

cleanup() {
  trap - INT TERM EXIT
  echo
  echo "→ Останавливаю серверы…"
  kill 0 2>/dev/null || true
}
trap cleanup INT TERM EXIT

(cd "$BACKEND" && exec .venv/bin/uvicorn app.main:app --reload --port 8000) &
(cd "$FRONTEND" && exec npm run dev -- --port "$FRONT_PORT" --strictPort) &

sleep 3
echo
echo "✓ Сайт:    http://localhost:$FRONT_PORT"
echo "✓ Swagger: http://localhost:8000/docs"
echo "  Вход: teacher / 1234 или student / 1234. Остановить: Ctrl+C"
echo
wait
