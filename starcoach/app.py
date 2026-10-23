"""FastAPI application: JSON API under /api and the mobile web app at /."""

import hashlib
import sqlite3
from collections.abc import Iterator
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from starcoach import __version__, api
from starcoach.config import Settings, get_settings
from starcoach.db import connect
from starcoach.filters import parse_filters
from starcoach.logs import log_event

WEB_DIR = Path(__file__).resolve().parent / "web"


def asset_version() -> str:
    h = hashlib.sha256()
    for name in ("app.js", "app.css"):
        h.update((WEB_DIR / "static" / name).read_bytes())
    return h.hexdigest()[:10]


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

    @app.get("/ready")
    def ready() -> JSONResponse:
        ok = settings.db_path.exists()
        return JSONResponse({"ready": ok}, status_code=200 if ok else 503)

    @app.get("/api/meta")
    def meta(conn: sqlite3.Connection = Depends(db)) -> dict:
        return api.meta(conn)

    @app.get("/api/compare")
    def compare(request: Request, ids: str = Query(..., max_length=500),
                conn: sqlite3.Connection = Depends(db)) -> dict:
        """ids: comma-separated product ids (2-3). Same filter params as /api/products/{id}."""
        return api.compare(conn, [i for i in ids.split(",") if i], parse_filters(dict(request.query_params)))

    gazetteer_cache: dict = {}

    @app.get("/api/ask")
    def ask(text: str = Query(..., min_length=1, max_length=300), conn: sqlite3.Connection = Depends(db)) -> dict:
        """A Persian sentence -> product words + filter patch + what was understood (rules; no LLM)."""
        from starcoach.intent import Gazetteer

        if "g" not in gazetteer_cache:
            gazetteer_cache["g"] = Gazetteer.from_db(conn)
        result = api.ask(conn, text, gazetteer_cache["g"])
        log_event(settings.log_dir, "ask", "ask", text=text, query=result["query"], filters=result["filters"],
                  intent=result["intent"])
        return result

    @app.get("/api/guide")
    def guide(request: Request, q: str = Query("", max_length=200), cat: str | None = None,
              conn: sqlite3.Connection = Depends(db)) -> dict:
        """Guided model choice. Answers come as a.<question id>=<value>; filters as in /api/products."""
        params = dict(request.query_params)
        answers = {k[2:]: v for k, v in params.items() if k.startswith("a.")}
        return api.guide(conn, q, answers, parse_filters(params), category=cat)

    @app.get("/api/areas")
    def areas(conn: sqlite3.Connection = Depends(db)) -> dict:
        return api.areas(conn)

    @app.get("/api/search")
    def search(request: Request, q: str = Query("", max_length=200), limit: int = Query(20, ge=1, le=50),
               conn: sqlite3.Connection = Depends(db)) -> dict:
        """Same filter params as /api/products/{id}."""
        params = dict(request.query_params)
        return api.search(conn, q, limit=limit, f=parse_filters(params), all_categories=params.get("all_cats") == "1")

    @app.get("/api/products/{product_id}")
    def product(product_id: str, request: Request, conn: sqlite3.Connection = Depends(db)) -> dict:
        """Query params: min_price, max_price, area, passage, lat, lon, radius_m, at, open,
        installments, torobpay, in_person_pay, fast, warranty, sort (price | distance)."""
        p = api.product(conn, product_id, parse_filters(dict(request.query_params)))
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
    def index() -> HTMLResponse:
        # stamp asset URLs with a content hash, so browsers never run a stale app.js / app.css after an update
        html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
        return HTMLResponse(html.replace("{{asset_version}}", asset_version()), headers={"Cache-Control": "no-cache"})

    app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")
    return app
