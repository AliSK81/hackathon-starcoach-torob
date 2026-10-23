"""`starcoach ai-demo`: run the AI layer live and write what it did, with timings, to results/ai-demo.txt.

This is the evidence for the Intelligence criterion: the same question answered by the keyword search and by the
AI layer side by side, and the agent's tool trail for whole shopping requests. It needs the LLM from `.env`.
"""

import time
from pathlib import Path

from starcoach import agent, ai
from starcoach.config import Settings
from starcoach.db import connect
from starcoach.filters import Filters
from starcoach.search import search_products

SEARCH_CASES = [
    "هندزفری",
    "برای دویدن هندزفری",
    "گوشیم بیرون زود خالی میشه",
    "کابل",
    "ابزار برای تعمیر موبایل",
    "کولر گازی خونه برق میره خراب نشه",
    "جی بی ال",
]
AGENT_CASES = [
    "نمیدونم چه هندزفری‌ای بخرم؛ برای ورزش، حدود ۳ میلیون",
    "شارژر اپل ۲۰ وات قسطی نزدیک علاءالدین، فردا عصر باز باشه؛ از دو فروشنده بپرس موجوده؟",
    "کت و شلوار مردانه کجا بخرم؟",
]


def generate(db_path: Path, settings: Settings, out: Path) -> dict:
    if not settings.llm_enabled:
        raise SystemExit("ai-demo needs LLM_BASE_URL, LLM_API_KEY and LLM_MODEL in .env")
    conn = connect(db_path, readonly=True)
    lines = ["# AI layer demo (live LLM) — keyword search vs. AI search, and the agent's tool trail", ""]
    search_ms, with_picks, new_total = [], 0, 0
    lines.append("## AI search (async next to the keyword search; the keyword list is on screen first)")
    for q in SEARCH_CASES:
        keyword = search_products(conn, q, limit=3)["items"]
        t = time.time()
        r = ai.search_assist(conn, q, Filters(), settings)
        ms = round((time.time() - t) * 1000)
        lines += ["", f"== {q}", "keyword: " + (" | ".join(i["title"][:42] for i in keyword) or "(nothing)")]
        if not r.get("ok"):
            lines.append(f"AI: failed ({r.get('reason')}) after {ms} ms")
            continue
        search_ms.append(ms)
        with_picks += bool(r["picks"])
        new_total += r["new_count"]
        lines.append(f"AI ({ms} ms): {r['interpretation']}")
        if r["clarify"]:
            lines.append("  clarify: " + r["clarify"]["question"] + " → " + " / ".join(o["label"] for o in r["clarify"]["options"]))
        for p in r["picks"]:
            lines.append(f"  {'NEW ' if p['ai_new'] else '    '}{p['title'][:56]} — {p['ai_reason']}")
    lines += ["", "## Agent (bounded tool loop; every card and number comes from the DB)"]
    agent_ms = []
    for text in AGENT_CASES:
        t = time.time()
        steps, final = [], None
        for ev in agent.run_agent(conn, settings, text, [], {}, None):
            if ev["event"] == "step":
                steps.append(ev["tool"])
            else:
                final = ev
        ms = round((time.time() - t) * 1000)
        agent_ms.append(ms)
        lines += ["", f"== {text}", f"{ms} ms · tools: {' → '.join(steps) or '-'}", f"reply: {final['reply']}",
                  f"cards: {', '.join(b['type'] for b in final['blocks']) or '-'} · conditions applied: "
                  f"{', '.join(final['ctx_patch']) or '-'} · numbers grounded: {final['grounded']} · degraded: {final['degraded']}"]
    summary = {"search_cases": len(SEARCH_CASES), "search_with_picks": with_picks, "search_new_products": new_total,
               "search_ai_ms_avg": round(sum(search_ms) / len(search_ms)) if search_ms else None,
               "agent_cases": len(AGENT_CASES), "agent_ms_avg": round(sum(agent_ms) / len(agent_ms))}
    lines += ["", "## Summary", str(summary)]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary
