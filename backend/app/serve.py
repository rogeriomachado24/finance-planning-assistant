"""The whole app on one server: the built UI at "/", the API at "/api".

    npm run build                                  (in frontend/)
    uvicorn app.serve:create_site --factory        (in backend/)   -> http://127.0.0.1:8000

`start.ps1` at the repository root does both. In development, run the Vite dev server
instead: it serves the UI with hot reload and forwards /api to `app.main:app`.
The UI calls /api/... in both setups, so it doesn't know which one it runs in.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from app.config import BACKEND_DIR
from app.main import create_app

FRONTEND_DIST = BACKEND_DIR.parent / "frontend" / "dist"


class SinglePageApp(StaticFiles):
    """Static files, except that unknown paths get index.html: /compare or /ask are routes
    of the Vue app, not files, so the browser must receive the app and let it route."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
            return await super().get_response("index.html", scope)


def create_site(api: FastAPI | None = None, dist: Path = FRONTEND_DIST) -> FastAPI:
    if not (dist / "index.html").exists():
        raise RuntimeError(f"No built frontend in {dist}: run `npm run build` in frontend/.")
    api = api or create_app()

    # A mounted app's startup code doesn't run by itself: run the API's (migrations,
    # assumption presets, model warm-up) as part of the site's.
    @asynccontextmanager
    async def lifespan(site: FastAPI) -> AsyncIterator[None]:
        async with api.router.lifespan_context(api):
            yield

    site = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    site.mount("/api", api)  # API docs: /api/docs
    site.mount("/", SinglePageApp(directory=dist, html=True))
    return site
