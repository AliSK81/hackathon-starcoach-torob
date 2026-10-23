"""Phase 6: alternatives (R7), in-passage location (R8), and the visit plan (R4).

All answers come from DB values. Hours are declared by shops; unknown stays unknown.
"""

import json
import sqlite3
from datetime import datetime, timedelta

from starcoach.address import floor_label
from starcoach.filters import Filters, distance_m, format_distance
from starcoach.hours import is_open_at, now_tehran, status_text

WALK_M_PER_MIN = 75.0  # 4.5 km/h
MINUTES_PER_STOP = 10
SAME_BUILDING_M = 60
MAX_ALTERNATIVES = 5
MAX_SUBSTITUTES = 4
SUBSTITUTE_PRICE_BAND = (0.6, 1.5)


def _shop_row(conn: sqlite3.Connection, shop_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM shops WHERE shop_id = ?", (shop_id,)).fetchone()


def _loads(v, default):
    return json.loads(v) if v else default


def _where(s: sqlite3.Row) -> str | None:
    parts = [f"{s['passage_kind']} {s['passage']}" if s["passage"] else None, floor_label(s["floor"]),
             f"واحد {s['unit']}" if s["unit"] else (f"پلاک {s['plaque']}" if s["plaque"] else None)]
    return "، ".join(p for p in parts if p) or None


def alternatives(conn: sqlite3.Connection, product_id: str, from_shop_id: str | None, at: datetime | None = None,
                 reason: str = "closed") -> dict:
    """Other sellers of the same product (open at `at`, same passage first, then nearest), then substitutes."""
    at = at or now_tehran()
    origin = _shop_row(conn, from_shop_id) if from_shop_id else None
    rows = conn.execute(
        """SELECT o.shop_id, MIN(CASE WHEN o.price_status = 'ok' THEN o.price END) AS price,
                  MAX(o.price_changed_at) AS last_change, s.*
           FROM offers o JOIN shops s ON s.shop_id = o.shop_id
           WHERE o.product_id = ? AND o.shop_id != ? GROUP BY o.shop_id""",
        (product_id, from_shop_id or ""),
    ).fetchall()
    sellers = []
    for r in rows:
        hours = _loads(r["hours"], None)
        open_ = is_open_at(hours, at)
        if open_ is False:
            continue  # closed at the visit time is not an alternative
        d = distance_m(origin["lat"], origin["lon"], r["lat"], r["lon"]) if origin and r["lat"] and origin["lat"] else None
        same_passage = bool(origin and origin["passage"] and r["passage"] == origin["passage"])
        sellers.append({
            "shop_id": r["shop_id"], "name": r["name"], "where": _where(r), "area": r["area"],
            "price": r["price"], "last_change": r["last_change"], "open_now": open_,
            "hours_status": status_text(hours, at)["text"], "distance_m": round(d) if d is not None else None,
            "same_passage": same_passage, "lat": r["lat"], "lon": r["lon"],
        })
    sellers.sort(key=lambda x: (not x["same_passage"], x["open_now"] is not True,
                                x["distance_m"] if x["distance_m"] is not None else 1e9, x["price"] or 1e18))
    for s in sellers:
        s["why"] = ("در همین پاساژ" if s["same_passage"] else
                    (format_distance(s["distance_m"]) + " از فروشگاه قبلی" if s["distance_m"] is not None else "فاصله نامشخص"))
    return {"product_id": product_id, "from_shop_id": from_shop_id, "reason": reason,
            "sellers": sellers[:MAX_ALTERNATIVES], "sellers_total": len(sellers),
            "substitutes": substitutes(conn, product_id, origin, at) if len(sellers) < 3 else []}


def substitutes(conn: sqlite3.Connection, product_id: str, origin: sqlite3.Row | None, at: datetime) -> list[dict]:
    """Similar products: same category, similar price, with sellers open at `at` (nearest to origin first)."""
    p = conn.execute("SELECT category, median_price, brand FROM products WHERE product_id = ?", (product_id,)).fetchone()
    if not p or p["median_price"] is None:
        return []
    lo, hi = p["median_price"] * SUBSTITUTE_PRICE_BAND[0], p["median_price"] * SUBSTITUTE_PRICE_BAND[1]
    cands = conn.execute(
        """SELECT product_id, title, brand, images, n_shops, median_price FROM products
           WHERE category = ? AND product_id != ? AND title_redacted = 0 AND median_price BETWEEN ? AND ?
           ORDER BY n_shops DESC LIMIT 30""",
        (p["category"], product_id, lo, hi),
    ).fetchall()
    out = []
    for c in cands:
        shops = conn.execute(
            "SELECT DISTINCT s.* FROM offers o JOIN shops s ON s.shop_id = o.shop_id WHERE o.product_id = ?",
            (c["product_id"],),
        ).fetchall()
        open_shops = [s for s in shops if is_open_at(_loads(s["hours"], None), at) is not False]
        if not open_shops:
            continue
        near = None
        if origin and origin["lat"]:
            dists = [distance_m(origin["lat"], origin["lon"], s["lat"], s["lon"]) for s in open_shops if s["lat"]]
            near = round(min(dists)) if dists else None
        diff = (c["median_price"] - p["median_price"]) / p["median_price"]
        why = [f"همان دسته ({p['category']})",
               "قیمت مشابه" if abs(diff) < 0.1 else (f"حدود {abs(diff) * 100:.0f}٪ {'ارزان‌تر' if diff < 0 else 'گران‌تر'}"),
               f"{len(open_shops)} فروشنده"]
        if near is not None:
            why.append(format_distance(near) + " از فروشگاه قبلی")
        out.append({"product_id": c["product_id"], "title": c["title"], "brand": c["brand"],
                    "image": (_loads(c["images"], []) or [None])[0], "median_price": c["median_price"],
                    "open_shops": len(open_shops), "nearest_m": near, "why": why})
    out.sort(key=lambda x: (x["nearest_m"] if x["nearest_m"] is not None else 1e9, -x["open_shops"]))
    return out[:MAX_SUBSTITUTES]


def in_passage(conn: sqlite3.Connection, shop_id: str, limit: int = 6) -> dict | None:
    """R8: where the shop is inside its passage, and which units are next to it on the same floor."""
    s = _shop_row(conn, shop_id)
    if s is None:
        return None
    out = {"shop_id": shop_id, "passage": s["passage"], "passage_kind": s["passage_kind"], "floor": s["floor"],
           "floor_label": floor_label(s["floor"]), "unit": s["unit"], "plaque": s["plaque"], "address": s["address"],
           "neighbours": [], "floor_shops": 0, "passage_shops": 0}
    if not s["passage"]:
        return out
    same = conn.execute(
        "SELECT shop_id, name, floor, unit, plaque, categories FROM shops WHERE passage = ? AND shop_id != ?",
        (s["passage"], shop_id),
    ).fetchall()
    out["passage_shops"] = len(same) + 1
    # a plaque shared by many shops in one passage is the building's street number, not a unit
    shared = sum(1 for r in same if s["plaque"] and r["plaque"] == s["plaque"])
    out["plaque_is_building"] = shared >= 2
    if out["plaque_is_building"]:
        same = [r for r in same if r["unit"] or r["plaque"] != s["plaque"]]
    if s["floor"] is not None:
        floor_mates = [r for r in same if r["floor"] == s["floor"]]
        out["floor_shops"] = len(floor_mates) + 1
    else:  # floor not in the address: neighbours by plaque/unit number in the same passage
        floor_mates = list(same)
        out["floor_shops"] = None

    def unit_no(r):
        v = (r["unit"] or r["plaque"] or "").split()[0] if (r["unit"] or r["plaque"]) else ""
        digits = "".join(ch for ch in v if ch.isdigit())
        return int(digits) if digits else None

    mine = unit_no(s) if not out["plaque_is_building"] or s["unit"] else None
    ranked = sorted(floor_mates, key=lambda r: abs(unit_no(r) - mine) if mine is not None and unit_no(r) is not None else 1e9)
    if mine is None:
        ranked = []  # no unit number to measure "next to" from; listing random units would mislead
    for r in ranked[:limit]:
        cats = _loads(r["categories"], [])
        out["neighbours"].append({"shop_id": r["shop_id"], "name": r["name"],
                                  "unit": r["unit"] or (f"پلاک {r['plaque']}" if r["plaque"] else None),
                                  "category": cats[0] if cats else None})
    return out


def plan(conn: sqlite3.Connection, shop_ids: list[str], start_at: datetime | None = None,
         start: tuple[float, float] | None = None, minutes_per_stop: int = MINUTES_PER_STOP) -> dict:
    """Order stops into a walk: nearest next stop, same-building stops together (by floor), open-at-arrival check."""
    start_at = start_at or now_tehran()
    shops = [r for sid in dict.fromkeys(shop_ids) if (r := _shop_row(conn, sid)) is not None]
    if not shops:
        return {"stops": [], "total_walk_m": 0, "warnings": []}
    remaining = list(shops)
    here = start
    if here is None:
        located = [s for s in remaining if s["lat"]]
        here = (located[0]["lat"], located[0]["lon"]) if located else None
    ordered = []
    while remaining:
        def cost(s):
            if here is None or not s["lat"]:
                return (1e9, 0)
            return (distance_m(here[0], here[1], s["lat"], s["lon"]), s["floor"] if s["floor"] is not None else 0)
        nxt = min(remaining, key=cost)
        # take every remaining stop in the same building now, lowest floor first
        building = [s for s in remaining if s is nxt or (nxt["passage"] and s["passage"] == nxt["passage"])
                    or (s["lat"] and nxt["lat"] and distance_m(s["lat"], s["lon"], nxt["lat"], nxt["lon"]) < SAME_BUILDING_M)]
        building.sort(key=lambda s: s["floor"] if s["floor"] is not None else 0)
        for s in building:
            ordered.append(s)
            remaining.remove(s)
        last = building[-1]
        if last["lat"]:
            here = (last["lat"], last["lon"])
    stops, clock, total, prev, warnings = [], start_at, 0.0, start, []
    for s in ordered:
        walk = distance_m(prev[0], prev[1], s["lat"], s["lon"]) if prev and s["lat"] else 0.0
        total += walk
        clock = clock + timedelta(minutes=walk / WALK_M_PER_MIN)
        hours = _loads(s["hours"], None)
        open_ = is_open_at(hours, clock)
        st = status_text(hours, clock)
        if open_ is False:
            warnings.append({"shop_id": s["shop_id"], "kind": "closed", "text": f"«{s['name']}» هنگام رسیدن بسته است ({st['text']})"})
        elif open_ is None:
            warnings.append({"shop_id": s["shop_id"], "kind": "unknown", "text": f"ساعت کاری «{s['name']}» ثبت نشده؛ قبل از رفتن بپرسید"})
        elif st.get("closes_in_min") is not None and st["closes_in_min"] < minutes_per_stop + 15:
            warnings.append({"shop_id": s["shop_id"], "kind": "closing", "text": f"«{s['name']}» {st['closes_in_min']} دقیقه بعد از رسیدن می‌بندد"})
        stops.append({"shop_id": s["shop_id"], "name": s["name"], "where": _where(s), "lat": s["lat"], "lon": s["lon"],
                      "arrive": clock.strftime("%H:%M"), "arrive_iso": clock.isoformat(timespec="minutes"),
                      "walk_m": round(walk), "open_on_arrival": open_, "hours_status": st["text"]})
        clock = clock + timedelta(minutes=minutes_per_stop)
        if s["lat"]:
            prev = (s["lat"], s["lon"])
    return {"start_at": start_at.isoformat(timespec="minutes"), "stops": stops, "total_walk_m": round(total),
            "finish": clock.strftime("%H:%M"), "warnings": warnings}


def filters_at(f: Filters | None) -> datetime:
    return f.at if f else now_tehran()
