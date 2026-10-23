"""R26: where in Tehran a kind of product is sold (its «بورس»), dataset first (R28).

1. Data: passages / areas with the most shops that listed products of the category, with open counts.
2. Known hubs: a cited outside list (Balad), labeled as outside knowledge.
3. LLM: only when the first two have nothing, labeled "check it".
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from starcoach.hours import is_open_at
from starcoach.textnorm import normalize, tokens

KNOWN_PATH = Path(__file__).resolve().parent / "data" / "known_hubs.json"
TOP_HUBS = 4
MIN_SHOPS = 3


def data_hubs(conn: sqlite3.Connection, category: str, at: datetime) -> list[dict]:
    rows = conn.execute(
        """SELECT DISTINCT s.shop_id, s.passage, s.passage_kind, s.area, s.lat, s.lon, s.hours
           FROM products p JOIN offers o ON o.product_id = p.product_id JOIN shops s ON s.shop_id = o.shop_id
           WHERE p.category = ?""",
        (category,),
    ).fetchall()
    groups: dict[tuple[str, str], dict] = {}
    for r in rows:
        kind, name = ("passage", r["passage"]) if r["passage"] else ("area", r["area"])
        if not name:
            continue
        g = groups.setdefault((kind, name), {"kind": kind, "name": name, "passage_kind": r["passage_kind"],
                                             "area": r["area"], "shops": 0, "open": 0, "lats": [], "lons": []})
        g["shops"] += 1
        g["open"] += is_open_at(json.loads(r["hours"]) if r["hours"] else None, at) is True
        if r["lat"]:
            g["lats"].append(r["lat"])
            g["lons"].append(r["lon"])
    out = []
    for g in sorted(groups.values(), key=lambda x: -x["shops"]):
        if g["shops"] < MIN_SHOPS:
            break
        lats, lons = sorted(g.pop("lats")), sorted(g.pop("lons"))
        g["lat"] = lats[len(lats) // 2] if lats else None  # median: robust to a few wrong pins
        g["lon"] = lons[len(lons) // 2] if lons else None
        g["source"] = "data"
        out.append(g)
        if len(out) >= TOP_HUBS:
            break
    return out


def known_hubs(text: str) -> dict | None:
    """The cited outside list entry whose keywords appear in `text` (a category name or a query)."""
    data = json.loads(KNOWN_PATH.read_text(encoding="utf-8"))
    words = set(tokens(text))
    norm = normalize(text)
    for hub in data["hubs"]:
        for kw in hub["match"]:
            k = normalize(kw)
            if (" " in k and k in norm) or k in words:
                return {"label": hub["label"], "places": hub["places"], "source": data["_source"]}
    return None


def llm_hubs(query: str, settings) -> dict | None:
    """Ask the LLM where in Tehran this is usually sold. Labeled as unverified model knowledge."""
    from starcoach.llm import LLMError, chat

    if not settings or not settings.llm_enabled or not query:
        return None
    messages = [
        {"role": "system", "content": "You know Tehran's traditional trade hubs (بورس) for kinds of goods. "
                                      "Answer only with JSON: {\"places\": [up to 3 short Persian place names in Tehran]}. "
                                      "If you are not sure, return {\"places\": []}."},
        {"role": "user", "content": f"کالا: {query}\nبورس این کالا در تهران کجاست؟"},
    ]
    try:
        msg = chat(settings, messages, max_tokens=120, purpose="hubs")
        text = (msg.get("content") or "").strip()
        start, end = text.find("{"), text.rfind("}")
        places = json.loads(text[start:end + 1]).get("places", []) if start >= 0 else []
    except (LLMError, ValueError):
        return None
    places = [p for p in places if isinstance(p, str) and 1 < len(p) < 60][:3]
    if not places:
        return None
    return {"places": places, "source": "llm", "note": "پیشنهاد هوش مصنوعی از دانش عمومی؛ در داده‌ی ترب نیست — قبل از رفتن بررسی کنید"}


def hubs(conn: sqlite3.Connection, category: str | None, query: str, at: datetime, settings=None) -> dict:
    found_data = data_hubs(conn, category, at) if category else []
    known = known_hubs(f"{category or ''} {query}")
    llm = llm_hubs(query or category or "", settings) if not found_data and not known else None
    return {"category": category, "query": query, "data_hubs": found_data, "known": known, "llm": llm}
