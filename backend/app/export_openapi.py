"""Write the API's OpenAPI description, from which the frontend generates its TypeScript types.

python -m app.export_openapi    # then, in frontend/: npm run api:types
"""

import json
import sys

from app.config import BACKEND_DIR
from app.main import create_app

OPENAPI_PATH = BACKEND_DIR.parent / "frontend" / "src" / "api" / "openapi.json"


def render_openapi() -> str:
    return json.dumps(create_app().openapi(), indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    OPENAPI_PATH.parent.mkdir(parents=True, exist_ok=True)
    OPENAPI_PATH.write_text(render_openapi(), encoding="utf-8", newline="\n")
    print(f"Wrote {OPENAPI_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
