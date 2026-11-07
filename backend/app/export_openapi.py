"""Сохраняет схему OpenAPI в файл: python -m app.export_openapi openapi.json

Из неё фронтенд генерирует типы (npm run gen:api).
"""

import json
import sys
from pathlib import Path

from app.main import create_app


def main() -> None:
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "openapi.json")
    schema = create_app(start_ticker=False).openapi()
    target.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OpenAPI сохранён в {target}")


if __name__ == "__main__":
    main()
