"""Regenerate the offline result files in results/ from the built DB, so reviewers can check every number."""

import json
import time
from datetime import datetime
from pathlib import Path

from starcoach import api, contact, visit
from starcoach.build import stats
from starcoach.db import connect
from starcoach.evaluate import EVAL_NOW, baseline_parse, run_eval
from starcoach.filters import parse_filters
from starcoach.hours import TEHRAN
from starcoach.intent import Gazetteer, parse_request
from starcoach.search import search_products

SEARCH_QUERIES = ["گوشی سامسونگ", "آیفون ۱۳ ۱۲۸", "هندزفری بلوتوث", "شارژر اپل ۲۰ وات", "s25 fe", "شیامی ردمی",
                  "جی بی ال", "محافظ برق کولر", "دزدگیر اماکن", "لپ تاپ ایسوس", "باتری ردمی", "هدفون بی سیم ارزان"]
GUIDE_QUERIES = ["کتونی", "گوشی", "لپ تاپ", "هندزفری", "ساعت مچی", "دوربین مداربسته"]
VISIT_AT = datetime(2026, 10, 24, 11, tzinfo=TEHRAN)  # a Saturday, 11:00
ALAEDDIN = (35.6950, 51.4113)


def _write(out: Path, name: str, text: str) -> str:
    (out / name).write_text(text, encoding="utf-8")
    return name


def generate(db_path: Path, cases: Path, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    conn = connect(db_path, readonly=True)
    written, started = [], time.time()

    written.append(_write(out, "stats.json", json.dumps(stats(db_path), ensure_ascii=False, indent=2)))

    lines, times = [], []
    for q in SEARCH_QUERIES:
        t = time.time()
        r = search_products(conn, q, limit=3)
        times.append((time.time() - t) * 1000)
        lines.append(f"== {q}  (words={r['words']} mode={r['mode']} total={r.get('total', 0)})")
        for it in r["items"]:
            price = f"{it['min_price']:,}" if it["min_price"] else "-"
            lines.append(f"   shops={it['n_shops']:<3} min={price:>14}  {it['title']}  [{it['category']}]")
    lines.append(f"\nmean query time: {sum(times) / len(times):.1f} ms over {len(times)} queries")
    written.append(_write(out, "search-demo-queries.txt", "\n".join(lines) + "\n"))

    g = Gazetteer.from_db(conn)
    evals = {}
    for split in ("dev", "test", "hard", "hard2"):
        evals[split] = {
            "baseline": run_eval(cases, baseline_parse, split),
            "rules": run_eval(cases, lambda t: parse_request(t, g, now=EVAL_NOW), split),
        }
    summary = {s: {k: {"exact": v["exact_match"], "slots": v["slot_accuracy"]} for k, v in e.items()} for s, e in evals.items()}
    written.append(_write(out, "intent-eval-rules.json", json.dumps({"summary": summary, "detail": evals}, ensure_ascii=False, indent=2)))

    lines = []
    for q in GUIDE_QUERIES:
        gd = api.guide(conn, q, {})
        lines.append(f"== {q} -> {gd['category']} ({gd['products']} models)")
        for qq in gd["questions"]:
            lines.append("  ? " + qq["text"] + " " + " | ".join(f"{o['label']}({o['count']})" for o in qq["options"]))
        for s in gd["suggestions"]:
            lines.append(f"  * {s['title']} | sellers {s['n_shops']} | median {s['median_price']:,} | {s['why']}")
    written.append(_write(out, "guide-demo.txt", "\n".join(lines) + "\n"))

    lines = []
    for q in ["شارژر اپل ۲۰ وات", "گوشی سامسونگ S25 FE"]:
        pid = api.search(conn, q)["items"][0]["product_id"]
        for label, params in [
            ("all", {}), ("installments only", {"installments": "1"}),
            ("near Alaeddin, by distance", {"lat": str(ALAEDDIN[0]), "lon": str(ALAEDDIN[1]), "sort": "distance"}),
            ("open + installments + 500 m", {"open": "1", "installments": "1", "lat": str(ALAEDDIN[0]),
                                             "lon": str(ALAEDDIN[1]), "radius_m": "500"}),
        ]:
            p = api.product(conn, pid, parse_filters({"at": VISIT_AT.strftime("%Y-%m-%dT%H:%M"), **params}))
            lines.append(f"== {q} | {label}: {len(p['sellers'])}/{p['sellers_total']} sellers")
            for e in p["sellers"][:3]:
                lines.append(f"   {e['best_price'] or '-'} | d={e['distance_m']} | " + " | ".join(r["text"] for r in e["reasons"]))
            for r in p["relax"]:
                lines.append(f"   relax: drop «{r['label']}» -> {r['sellers']} sellers")
    written.append(_write(out, "filters-demo.txt", "\n".join(lines) + "\n"))

    lines = []
    pid = api.search(conn, "گوشی سامسونگ S25 FE")["items"][0]["product_id"]
    p = api.product(conn, pid, parse_filters({"at": VISIT_AT.strftime("%Y-%m-%dT%H:%M"), "passage": "علاءالدین"}))
    lines.append(f"S25 FE sellers in علاءالدین: {len(p['sellers'])}")
    for e in p["sellers"][:3]:
        r = contact.contact(conn, e["offers"][0]["offer_id"], ["in_stock", "price_now", "hours_today", "hold"],
                            VISIT_AT, now=VISIT_AT)
        lines.append(f"- contact {r['shop_name']}: {r['reply']['status']} | {r['reply']['text']}")
    first = p["sellers"][0]["shop"]["shop_id"]
    alt = visit.alternatives(conn, pid, first, VISIT_AT, "no_answer")
    lines.append(f"alternatives if the first does not answer: {alt['sellers_total']} open sellers")
    for s in alt["sellers"]:
        lines.append(f"   {s['name']} | {s['where']} | {s['price']} | {s['why']}")
    pl = visit.plan(conn, [e["shop"]["shop_id"] for e in p["sellers"][:3]], VISIT_AT, start=ALAEDDIN)
    lines.append(f"plan: {len(pl['stops'])} stops, {pl['total_walk_m']} m, finish {pl['finish']}")
    for st in pl["stops"]:
        lines.append(f"   {st['arrive']} {st['name']} | {st['where']} | {st['hours_status']}")
    lines.extend("   ! " + w["text"] for w in pl["warnings"])
    written.append(_write(out, "visit-demo.txt", "\n".join(lines) + "\n"))

    return {"written": written, "seconds": round(time.time() - started, 1), "intent_summary": summary}
