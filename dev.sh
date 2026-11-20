#!/usr/bin/env bash
# Локальная разработка: PostgreSQL, миграции, backend и frontend одной командой.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
FRONT_PORT="${FRONT_PORT:-5173}"
SEED_DEMO=false
EXTERNAL_DB=false
BACK_PID=""
FRONT_PID=""
DB_MANAGED=false

usage() {
  cat <<'EOF'
Использование: ./dev.sh [--seed] [--external-db]
               ./dev.sh --setup [frontend|backend]

  --setup        Установить зависимости обеих частей или выбранной части и выйти.

  --seed         Создать демо-аккаунты, дисциплину и очередь (повторный вызов
                 обновляет пароли демо-аккаунтов).
  --external-db  Не запускать PostgreSQL в Docker; использовать DATABASE_URL
                 из backend/.env или переменной окружения.
  -h, --help     Показать эту справку.

По умолчанию: поднять PostgreSQL через Docker Compose, применить миграции,
запустить backend на :8000 и frontend на :5173.
Другой порт frontend: FRONT_PORT=5174 ./dev.sh
EOF
}

fail() {
  echo "✗ $*" >&2
  exit 1
}

setup_backend() {
  command -v python3 >/dev/null 2>&1 || fail "Нужен Python 3.12 или новее."
  python3 -c 'import sys; sys.exit(sys.version_info < (3, 12))' ||
    fail "Нужен Python 3.12 или новее (сейчас: $(python3 --version 2>&1))."
  if [ ! -x "$BACKEND/.venv/bin/python" ]; then
    echo "→ Создаю Python-окружение…"
    python3 -m venv "$BACKEND/.venv"
  fi
  "$BACKEND/.venv/bin/python" -c 'import sys; sys.exit(sys.version_info < (3, 12))' ||
    fail "backend/.venv создан с устаревшим Python. Пересоздайте окружение с Python 3.12+."
  if [ ! -x "$BACKEND/.venv/bin/uvicorn" ] ||
     ! cmp -s "$BACKEND/pyproject.toml" "$BACKEND/.venv/.labflow-pyproject.toml"; then
    echo "→ Устанавливаю зависимости backend…"
    "$BACKEND/.venv/bin/python" -m pip install -e "$BACKEND[dev]"
    cp "$BACKEND/pyproject.toml" "$BACKEND/.venv/.labflow-pyproject.toml"
  fi
}

setup_frontend() {
  command -v node >/dev/null 2>&1 || fail "Нужен Node.js 24. Установите его и повторите запуск."
  node -e 'process.exit(Number(process.versions.node.split(".")[0]) >= 24 ? 0 : 1)' ||
    fail "Нужен Node.js 24 или новее (сейчас: $(node --version)). Выполните nvm use, если используете nvm."
  command -v npm >/dev/null 2>&1 || fail "Не найден npm. Установите Node.js 24 вместе с npm."
  if [ ! -x "$FRONTEND/node_modules/.bin/vite" ] ||
     ! cmp -s "$FRONTEND/package.json" "$FRONTEND/node_modules/.labflow-package.json" ||
     ! cmp -s "$FRONTEND/package-lock.json" "$FRONTEND/node_modules/.labflow-package-lock.json"; then
    echo "→ Устанавливаю зависимости frontend из package-lock.json…"
    (cd "$FRONTEND" && npm ci)
    cp "$FRONTEND/package.json" "$FRONTEND/node_modules/.labflow-package.json"
    cp "$FRONTEND/package-lock.json" "$FRONTEND/node_modules/.labflow-package-lock.json"
  fi
}

if [ "${1:-}" = --setup ]; then
  [ "$#" -le 2 ] || { usage >&2; exit 2; }
  case "${2-}" in
    "") setup_backend; setup_frontend ;;
    backend) setup_backend ;;
    frontend) setup_frontend ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
  echo "✓ Зависимости готовы."
  exit 0
fi

for arg in "$@"; do
  case "$arg" in
    --seed) SEED_DEMO=true ;;
    --external-db) EXTERNAL_DB=true ;;
    -h|--help) usage; exit 0 ;;
    *) echo "✗ Неизвестный аргумент: $arg" >&2; usage >&2; exit 2 ;;
  esac
done

if [ "$EXTERNAL_DB" = false ]; then
  command -v docker >/dev/null 2>&1 || fail "Нужен Docker с Compose. Для своей БД используйте --external-db."
  docker compose version >/dev/null 2>&1 ||
    fail "Не найден Docker Compose. Для своей БД используйте --external-db."
  docker info >/dev/null 2>&1 ||
    fail "Docker не запущен или недоступен. Запустите Docker и повторите попытку."
fi

command -v python3 >/dev/null 2>&1 || fail "Нужен Python 3.12 или новее."
[[ "$FRONT_PORT" =~ ^[0-9]+$ ]] &&
  python3 -c 'import sys; sys.exit(not 1 <= int(sys.argv[1]) <= 65535)' "$FRONT_PORT" ||
  fail "FRONT_PORT должен быть числом от 1 до 65535."
[ "$FRONT_PORT" != 8000 ] || fail "FRONT_PORT не может быть 8000: этот порт занят backend."

# Проверяем порты до установки зависимостей и запуска БД.
for port in 8000 "$FRONT_PORT"; do
  if ! python3 -c 'import socket, sys; s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind(("127.0.0.1", int(sys.argv[1]))); s.close()' "$port" 2>/dev/null; then
    fail "Порт $port занят. Остановите другой сервер или задайте FRONT_PORT для frontend."
  fi
done

if [ ! -f "$BACKEND/.env" ]; then
  cp "$BACKEND/.env.example" "$BACKEND/.env"
  echo "→ Создан backend/.env из примера."
fi

setup_backend
setup_frontend

cleanup() {
  trap - EXIT HUP INT TERM
  if [ -n "$BACK_PID" ] || [ -n "$FRONT_PID" ]; then
    echo
    echo "→ Останавливаю серверы…"
  fi
  if [ -n "$BACK_PID" ]; then kill "$BACK_PID" 2>/dev/null || true; fi
  if [ -n "$FRONT_PID" ]; then kill "$FRONT_PID" 2>/dev/null || true; fi
  if [ -n "$BACK_PID" ]; then wait "$BACK_PID" 2>/dev/null || true; fi
  if [ -n "$FRONT_PID" ]; then wait "$FRONT_PID" 2>/dev/null || true; fi
  if [ "$DB_MANAGED" = true ]; then
    echo "→ Останавливаю PostgreSQL…"
    (cd "$ROOT" && docker compose stop db) ||
      echo "✗ Не удалось остановить PostgreSQL. Выполните docker compose stop db." >&2
  fi
}
trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

if [ "$EXTERNAL_DB" = false ]; then
  running_db="$(cd "$ROOT" && docker compose ps --status running -q db)" ||
    fail "Не удалось определить состояние PostgreSQL через Docker Compose."
  if [ -n "$running_db" ]; then
    echo "→ Использую уже запущенную PostgreSQL…"
    (cd "$ROOT" && docker compose up -d --no-recreate --wait db) ||
      fail "PostgreSQL не готова. Проверьте docker compose ps db."
  else
    DB_MANAGED=true
    echo "→ Поднимаю PostgreSQL…"
    (cd "$ROOT" && docker compose up -d --wait db) ||
      fail "Не удалось запустить PostgreSQL. Проверьте Docker и вывод docker compose ps db."
  fi
  DB_ADDRESS="$(cd "$ROOT" && docker compose port db 5432)" ||
    fail "Не удалось определить порт PostgreSQL через Docker Compose."
  DB_PORT="${DB_ADDRESS##*:}"
  [[ "$DB_PORT" =~ ^[0-9]+$ ]] || fail "Некорректный порт PostgreSQL: $DB_ADDRESS"
  export DATABASE_URL="postgresql+asyncpg://labflow:labflow@127.0.0.1:$DB_PORT/labflow"
  echo "→ PostgreSQL доступен на 127.0.0.1:$DB_PORT."
else
  echo "→ Использую внешнюю БД из DATABASE_URL."
fi

echo "→ Применяю миграции…"
(cd "$BACKEND" && .venv/bin/alembic upgrade head) ||
  fail "Не удалось применить миграции. Проверьте DATABASE_URL и доступность БД."

if [ "$SEED_DEMO" = true ]; then
  echo "→ Создаю демо-данные…"
  (cd "$BACKEND" && .venv/bin/python -m app.seed)
fi

echo "→ Запускаю backend и frontend…"
(cd "$BACKEND" && exec .venv/bin/uvicorn app.main:app --reload --port 8000) &
BACK_PID=$!
(cd "$FRONTEND" && exec ./node_modules/.bin/vite --host 127.0.0.1 --port "$FRONT_PORT" --strictPort) &
FRONT_PID=$!

wait_for_url() {
  local label="$1" url="$2" pid="$3"
  for ((attempt = 0; attempt < 40; attempt++)); do
    kill -0 "$pid" 2>/dev/null || fail "$label завершился при запуске."
    if python3 -c 'import sys, urllib.request; urllib.request.urlopen(sys.argv[1], timeout=1).close()' "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.5
  done
  fail "$label не ответил после ожидания: $url"
}

wait_for_url "Backend" "http://127.0.0.1:8000/health" "$BACK_PID"
wait_for_url "Frontend" "http://127.0.0.1:$FRONT_PORT/" "$FRONT_PID"

echo
echo "✓ Сайт:    http://localhost:$FRONT_PORT"
echo "✓ Swagger: http://localhost:8000/docs"
if [ "$SEED_DEMO" = true ]; then
  echo "  Демо-логины: teacher, student, admin. Локальный пароль по умолчанию: 1234"
else
  echo "  Демо-данные: остановите серверы и запустите ./dev.sh --seed"
fi
echo "  Остановить: Ctrl+C"
echo

if wait -n "$BACK_PID" "$FRONT_PID"; then
  fail "Один из серверов завершился."
else
  fail "Один из серверов завершился с ошибкой."
fi
