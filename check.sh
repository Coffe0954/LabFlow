#!/usr/bin/env bash
# Локальные проверки перед PR. --postgres дополнительно проверяет миграции и тесты на PostgreSQL.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
SCOPE=all
POSTGRES=false
CHECK_PROJECT=""
CHECK_TMP=""

usage() {
  cat <<'EOF'
Использование: ./check.sh [frontend|backend] [--postgres]

  без аргументов  Полная проверка обеих частей, тесты backend на SQLite.
  frontend        Типы API из backend/openapi.json, линтер, тесты и сборка.
  backend         Линтер, форматирование, типы, тесты на SQLite и схема OpenAPI.
  --postgres      Проверить миграции и выполнить тесты backend на временной
                  PostgreSQL вместо SQLite. Доступно для backend и полной проверки.
  -h, --help      Показать эту справку.

Установить зависимости: ./dev.sh --setup [frontend|backend]
EOF
}

for arg in "$@"; do
  case "$arg" in
    frontend|backend)
      [ "$SCOPE" = all ] || { usage >&2; exit 2; }
      SCOPE="$arg" ;;
    --postgres) POSTGRES=true ;;
    -h|--help) usage; exit 0 ;;
    *) echo "✗ Неизвестный аргумент: $arg" >&2; usage >&2; exit 2 ;;
  esac
done

if [ "$SCOPE" = frontend ] && [ "$POSTGRES" = true ]; then
  echo "Флаг --postgres применим только к проверкам backend." >&2
  exit 2
fi

fail() {
  echo "✗ $*" >&2
  exit 1
}

check_compose() {
  docker compose -f "$ROOT/docker-compose.yml" -p "$CHECK_PROJECT" "$@"
}

cleanup() {
  local result=$?
  trap - EXIT HUP INT TERM
  if [ -n "$CHECK_PROJECT" ]; then
    echo "→ Удаляю временный контейнер PostgreSQL…"
    check_compose down -v --remove-orphans || {
      echo "✗ Не удалось удалить временный контейнер $CHECK_PROJECT" >&2
      result=1
    }
  fi
  if [ -n "$CHECK_TMP" ]; then
    rm -rf -- "$CHECK_TMP" || {
      echo "✗ Не удалось удалить временные файлы $CHECK_TMP" >&2
      result=1
    }
  fi
  if [ "$result" -eq 0 ]; then echo "✓ Выбранные проверки прошли."; fi
  exit "$result"
}
trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

check_backend() {
  command -v python3 >/dev/null 2>&1 || fail "Нужен Python 3.12 или новее."
  python3 -c 'import sys; sys.exit(sys.version_info < (3, 12))' ||
    fail "Нужен Python 3.12 или новее."
  for tool in ruff mypy pytest alembic; do
    [ -x "$BACKEND/.venv/bin/$tool" ] || fail "Не найдены зависимости backend. Сначала запустите ./dev.sh --setup backend."
  done
  cmp -s "$BACKEND/pyproject.toml" "$BACKEND/.venv/.labflow-pyproject.toml" ||
    fail "Зависимости backend изменились. Запустите ./dev.sh --setup backend для обновления окружения."

  echo "→ Backend: линтер, форматирование и типы…"
  (cd "$BACKEND" && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy app)

  if [ "$POSTGRES" = true ]; then
    command -v docker >/dev/null 2>&1 || fail "Для --postgres нужен Docker с Compose."
    docker compose version >/dev/null 2>&1 || fail "Для --postgres нужен Docker Compose."
    docker info >/dev/null 2>&1 || fail "Docker не запущен или недоступен."
    CHECK_PROJECT="labflow-check-$(date +%s)-$$"
    echo "→ Поднимаю отдельный PostgreSQL на свободном порту…"
    check_compose up -d --wait db
    check_compose exec -T db createdb -U labflow labflow_test
    db_endpoint="$(check_compose port db 5432)"
    db_port="${db_endpoint##*:}"
    [[ "$db_port" =~ ^[0-9]+$ ]] || fail "Не удалось определить порт тестовой БД."
    export DATABASE_URL="postgresql+asyncpg://labflow:labflow@127.0.0.1:$db_port/labflow_test"
    export TEST_DATABASE_URL="$DATABASE_URL"
    echo "→ Backend: миграции и тесты на PostgreSQL…"
    (cd "$BACKEND" && .venv/bin/alembic upgrade head && .venv/bin/alembic check &&
      .venv/bin/alembic downgrade base && .venv/bin/pytest -q)
  else
    echo "→ Backend: тесты на SQLite…"
    (cd "$BACKEND" && unset TEST_DATABASE_URL && .venv/bin/pytest -q)
  fi

  echo "→ Проверяю актуальность OpenAPI…"
  (cd "$BACKEND" && .venv/bin/python -m app.export_openapi "$CHECK_TMP/openapi.json")
  cmp -s "$CHECK_TMP/openapi.json" "$BACKEND/openapi.json" ||
    fail "backend/openapi.json устарел. Обновите: cd backend && .venv/bin/python -m app.export_openapi openapi.json"
}

check_frontend() {
  command -v node >/dev/null 2>&1 || fail "Нужен Node.js 24 или новее."
  node -e 'process.exit(Number(process.versions.node.split(".")[0]) >= 24 ? 0 : 1)' ||
    fail "Нужен Node.js 24 или новее (сейчас: $(node --version)). Выполните nvm use, если используете nvm."
  command -v npm >/dev/null 2>&1 || fail "Не найден npm."
  for tool in openapi-typescript eslint prettier vitest tsc vite; do
    [ -x "$FRONTEND/node_modules/.bin/$tool" ] || fail "Не найдены зависимости frontend. Сначала запустите ./dev.sh --setup frontend."
  done
  cmp -s "$FRONTEND/package.json" "$FRONTEND/node_modules/.labflow-package.json" ||
    fail "Зависимости frontend изменились. Запустите ./dev.sh --setup frontend для обновления окружения."
  cmp -s "$FRONTEND/package-lock.json" "$FRONTEND/node_modules/.labflow-package-lock.json" ||
    fail "Зависимости frontend изменились. Запустите ./dev.sh --setup frontend для обновления окружения."

  echo "→ Проверяю типы frontend по OpenAPI…"
  (cd "$FRONTEND" && ./node_modules/.bin/openapi-typescript "$BACKEND/openapi.json" -o "$CHECK_TMP/schema.d.ts")
  cmp -s "$CHECK_TMP/schema.d.ts" "$FRONTEND/src/api/schema.d.ts" ||
    fail "frontend/src/api/schema.d.ts устарел. Обновите: cd frontend && npm run gen:api"

  echo "→ Frontend: линтер, тесты и сборка…"
  (cd "$FRONTEND" && npm run lint && npm run test && npm run build)
}

CHECK_TMP="$(mktemp -d)"
if [ "$SCOPE" != frontend ]; then check_backend; fi
if [ "$SCOPE" != backend ]; then check_frontend; fi
