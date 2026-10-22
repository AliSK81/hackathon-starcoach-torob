"""FastAPI application: JSON API under /api and the mobile web app at /."""

import sqlite3
from collections.abc import Iterator
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from starcoach import __version__, api
from starcoach.config import Settings, get_settings
from starcoach.db import connect

WEB_DIR = Path(__file__).resolve().parent / "web"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="StarCoach", version=__version__)
    app.state.settings = settings

    def db() -> Iterator[sqlite3.Connection]:
        if not settings.db_path.exists():
            raise HTTPException(503, "database not built; run `starcoach build-db`")
        conn = connect(settings.db_path, readonly=True)
        try:
            yield conn
        finally:
            conn.close()

    @app.get("/health")
    def health() -> dict:
        return {
            "status": "ok",
            "version": __version__,
            "db": settings.db_path.exists(),
            "llm": settings.llm_enabled,
        }

    @app.get("/api/meta")
    def meta(conn: sqlite3.Connection = Depends(db)) -> dict:
        return api.meta(conn)

    @app.get("/api/search")
    def search(q: str = Query("", max_length=200), limit: int = Query(20, ge=1, le=50),
               conn: sqlite3.Connection = Depends(db)) -> dict:
        return api.search(conn, q, limit=limit)

    @app.get("/api/products/{product_id}")
    def product(product_id: str, conn: sqlite3.Connection = Depends(db)) -> dict:
        p = api.product(conn, product_id)
        if p is None:
            raise HTTPException(404, "product not found")
        return p

    @app.get("/api/shops/{shop_id}")
    def shop(shop_id: str, conn: sqlite3.Connection = Depends(db)) -> dict:
        s = api.shop(conn, shop_id)
        if s is None:
            raise HTTPException(404, "shop not found")
        return s

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")
    return app
