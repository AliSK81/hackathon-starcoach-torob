"""R27: two-sided seller contact (mock channel). Buyer questions go to a seller inbox; the seller answers in one tap.

State is an append-only JSONL event log (rule 7), replayed at start, so a restart keeps the inbox and a retried
request is never recorded twice. A recent answer for the same offer is reused, so the seller isn't asked twice.
"""

import json
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from starcoach.hours import TEHRAN, now_tehran

REUSE_HOURS = 3  # answers younger than this are reused instead of asking the seller again


class Inbox:
    def __init__(self, log_path: Path):
        self.path = log_path
        self.requests: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                self._apply(json.loads(line))
            except (ValueError, KeyError):
                continue  # a broken line is skipped, never fatal

    def _apply(self, ev: dict) -> None:
        if ev["event"] == "created" and ev["request"]["id"] not in self.requests:
            self.requests[ev["request"]["id"]] = ev["request"]
        elif ev["event"] == "answered" and ev["id"] in self.requests:
            self.requests[ev["id"]].update(status="answered", answer=ev["answer"], answered_at=ev["at"])

    def _append(self, ev: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        self._apply(ev)

    def recent_answer(self, offer_id: str, now: datetime | None = None) -> dict | None:
        now = now or now_tehran()
        best = None
        for r in self.requests.values():
            if r["offer_id"] == offer_id and r["status"] == "answered":
                at = datetime.fromisoformat(r["answered_at"])
                if now - at <= timedelta(hours=REUSE_HOURS) and (best is None or r["answered_at"] > best["answered_at"]):
                    best = r
        return best

    def create(self, request_id: str | None, offer_id: str, shop_id: str, product_id: str, product_title: str,
               recorded_price: int | None, questions: list[str], message: str, visit_at: str | None) -> dict:
        with self._lock:
            rid = request_id or uuid.uuid4().hex
            if rid in self.requests:
                return self.requests[rid]  # a retry never records twice
            req = {"id": rid, "offer_id": offer_id, "shop_id": shop_id, "product_id": product_id,
                   "product_title": product_title, "recorded_price": recorded_price, "questions": questions,
                   "message": message, "visit_at": visit_at, "status": "waiting",
                   "created_at": now_tehran().isoformat(timespec="seconds")}
            self._append({"event": "created", "request": req})
            return self.requests[rid]

    def answer(self, request_id: str, in_stock: bool, price_now: int | None, hold_until: str | None,
               note: str | None) -> dict | None:
        with self._lock:
            req = self.requests.get(request_id)
            if req is None:
                return None
            if req["status"] == "answered":
                return req  # first answer wins; a double tap does not record twice
            ans = {"in_stock": in_stock, "price_now": price_now, "hold_until": hold_until, "note": (note or "")[:200]}
            self._append({"event": "answered", "id": request_id, "answer": ans,
                          "at": datetime.now(TEHRAN).isoformat(timespec="seconds")})
            return self.requests[request_id]

    def for_shop(self, shop_id: str) -> list[dict]:
        items = [r for r in self.requests.values() if r["shop_id"] == shop_id]
        return sorted(items, key=lambda r: (r["status"] != "waiting", r["created_at"]), reverse=False)
