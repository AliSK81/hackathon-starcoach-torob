"""FastAPI application: JSON API under /api and the mobile web app at /."""

import hashlib
import sqlite3
from collections.abc import Iterator
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from pydantic import BaseModel, Field

from starcoach import __version__, api, contact, visit
from starcoach.config import Settings, get_settings
from starcoach.db import connect
from starcoach.filters import parse_filters
from starcoach.logs import log_event

WEB_DIR = Path(__file__).resolve().parent / "web"


class ContactRequest(BaseModel):
    offer_id: str = Field(max_length=100)
    questions: list[str] = Field(default_factory=list, max_length=8)
    visit_at: str | None = Field(default=None, max_length=30)
    request_id: str | None = Field(default=None, max_length=64)


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
    def ask(text: str = Query(..., min_length=1, max_length=300), llm: bool = False,
            conn: sqlite3.Connection = Depends(db)) -> dict:
        """A Persian sentence -> product words + filter patch + what was understood.
        Rules by default; llm=1 adds the LLM step (only if configured)."""
        from starcoach.intent import Gazetteer

        if "g" not in gazetteer_cache:
            gazetteer_cache["g"] = Gazetteer.from_db(conn)
        result = api.ask(conn, text, gazetteer_cache["g"], settings=settings, use_llm=llm)
        log_event(settings.log_dir, "ask", "ask", text=text, query=result["query"], filters=result["filters"],
                  intent=result["intent"], source=result["source"], llm_error=result.get("llm_error"))
        return result

    @app.get("/api/guide")
    def guide(request: Request, q: str = Query("", max_length=200), cat: str | None = None,
              conn: sqlite3.Connection = Depends(db)) -> dict:
        """Guided model choice. Answers come as a.<question id>=<value>; filters as in /api/products."""
        params = dict(request.query_params)
        answers = {k[2:]: v for k, v in params.items() if k.startswith("a.")}
        return api.guide(conn, q, answers, parse_filters(params), category=cat)

    @app.get("/api/alternatives")
    def alternatives(product_id: str, shop_id: str | None = None, reason: str = "closed", at: str | None = None,
                     conn: sqlite3.Connection = Depends(db)) -> dict:
        """R7: other sellers of the product (open at `at`, same passage first), then substitute products."""
        return visit.alternatives(conn, product_id, shop_id, parse_filters({"at": at}).at, reason)

    @app.get("/api/shops/{shop_id}/where")
    def where(shop_id: str, conn: sqlite3.Connection = Depends(db)) -> dict:
        """R8: floor, unit and neighbouring units inside the shop's passage."""
        w = visit.in_passage(conn, shop_id)
        if w is None:
            raise HTTPException(404, "shop not found")
        return w

    contacts_seen: dict[str, dict] = {}

    @app.post("/api/contact")
    def contact_seller(body: ContactRequest, conn: sqlite3.Connection = Depends(db)) -> dict:
        """R5/R6: draft a message to the seller and return a SIMULATED reply (phones are fake, D6)."""
        if body.request_id and body.request_id in contacts_seen:
            return contacts_seen[body.request_id]  # a retry never records twice
        visit_at = parse_filters({"at": body.visit_at}).at if body.visit_at else None
        result = contact.contact(conn, body.offer_id, body.questions, visit_at)
        if result is None:
            raise HTTPException(404, "offer not found")
        if body.request_id:
            contacts_seen[body.request_id] = result
        log_event(settings.log_dir, "contacts", "contact", request_id=body.request_id, offer_id=body.offer_id,
                  shop_id=result["shop_id"], questions=result["questions"], status=result["reply"]["status"],
                  facts=result["reply"]["facts"], simulated=True)
        return result

    @app.get("/api/plan")
    def plan(shops: str = Query(..., max_length=2000), at: str | None = None, lat: float | None = None,
             lon: float | None = None, conn: sqlite3.Connection = Depends(db)) -> dict:
        """Order stops (comma-separated shop ids) into a walk with arrival times and open checks."""
        start = (lat, lon) if lat is not None and lon is not None else None
        return visit.plan(conn, [x for x in shops.split(",") if x], parse_filters({"at": at}).at, start)

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
