"""Product search: SQLite FTS5 over normalized text, with aliases and re-ranking (research 03 §2, F20)."""

import json
import math
import sqlite3
from functools import lru_cache
from pathlib import Path

from starcoach.textnorm import STOPWORDS, normalize, tokens

ALIASES_PATH = Path(__file__).resolve().parent / "data" / "aliases.json"
CANDIDATES = 400
HEAD_BOOST = 6.0  # title starts with a query word: «گوشی سامسونگ» prefers phones over «باتری گوشی …»
POPULARITY_WEIGHT = 1.0  # log(1 + shops)
ACCESSORY_PENALTY = 5.0  # «شیامی ردمی» should prefer phones over «باتری … ردمی» unless asked
ACCESSORY_HEADS = frozenset(normalize(w) for w in (
    "باتری باطری قاب کاور گلس محافظ فلت کابل شارژر کیف بند برد تاچ سوکت "
    "پایه نگهدارنده هولدر استند برچسب اسکرین آداپتور مبدل درب شاسی قطعه قطعات یدکی لوازم"
).split())
FTS_SCHEMA = """
CREATE VIRTUAL TABLE products_fts USING fts5(
    title, alias, brand, category,
    content='', tokenize='unicode61 remove_diacritics 2', prefix='2 3'
);
INSERT INTO products_fts(products_fts, rank) VALUES('rank', 'bm25(4.0, 2.0, 2.0, 1.0)');
"""


@lru_cache(maxsize=1)
def _alias_index() -> tuple[dict[tuple[str, ...], int], list[list[str]], int]:
    groups = json.loads(ALIASES_PATH.read_text(encoding="utf-8"))["groups"]
    index: dict[tuple[str, ...], int] = {}
    for gi, group in enumerate(groups):
        for phrase in group:
            key = tuple(tokens(phrase))
            if key:
                index.setdefault(key, gi)
    longest = max(len(k) for k in index)
    return index, groups, longest


def alias_tokens(toks: list[str]) -> list[str]:
    """Tokens of every alias of every phrase found in `toks`, minus tokens already there."""
    index, groups, longest = _alias_index()
    found = set()
    for n in range(1, longest + 1):
        for i in range(len(toks) - n + 1):
            gi = index.get(tuple(toks[i : i + n]))
            if gi is not None:
                found.add(gi)
    have = set(toks)
    extra: list[str] = []
    for gi in sorted(found):
        for phrase in groups[gi]:
            for t in tokens(phrase):
                if t not in have and t not in extra:
                    extra.append(t)
    return extra


def build_index(conn: sqlite3.Connection) -> int:
    """Create products_fts and products.head. Redacted titles are not indexed."""
    conn.executescript(FTS_SCHEMA)
    rows = []
    heads = []
    for rowid, title, brand, category in conn.execute(
        "SELECT rowid, title, brand, category FROM products WHERE title_redacted = 0"
    ):
        toks = tokens(title)
        brand_toks = tokens(brand)
        rows.append((rowid, " ".join(toks), " ".join(alias_tokens(toks + brand_toks)), " ".join(brand_toks),
                     normalize(category)))
        heads.append((toks[0] if toks else None, rowid))
    conn.executemany("INSERT INTO products_fts(rowid, title, alias, brand, category) VALUES (?,?,?,?,?)", rows)
    conn.executemany("UPDATE products SET head = ? WHERE rowid = ?", heads)
    conn.execute("INSERT INTO products_fts(products_fts) VALUES('optimize')")
    return len(rows)


def _match_expr(words: list[str], op: str) -> str:
    terms = [f'"{w}"' for w in words]
    terms[-1] += "*"
    return f" {op} ".join(terms)


def collapse_aliases(words: list[str]) -> list[str]:
    """Replace a multi-word alias (جی بی ال) with its one-word form (jbl), so its letters don't match alone."""
    index, groups, longest = _alias_index()
    out: list[str] = []
    i = 0
    while i < len(words):
        for n in range(min(longest, len(words) - i), 1, -1):
            gi = index.get(tuple(words[i : i + n]))
            single = next((p for p in groups[gi] if len(tokens(p)) == 1), None) if gi is not None else None
            if single:
                out.append(tokens(single)[0])
                i += n
                break
        else:
            out.append(words[i])
            i += 1
    return out


def query_words(query: str) -> list[str]:
    return collapse_aliases([t for t in tokens(query) if t not in STOPWORDS])


def search_products(conn: sqlite3.Connection, query: str, limit: int = 20) -> dict:
    """Return {"words", "mode": "and"|"or"|"none", "items": [product dicts with score]}."""
    words = query_words(query)
    if not words:
        return {"words": [], "mode": "none", "items": []}
    mode = "and"
    hits = _fts(conn, _match_expr(words, "AND"))
    if not hits:
        mode = "or"
        hits = _fts(conn, _match_expr(words, "OR"))
    if not hits:
        return {"words": words, "mode": "none", "items": []}
    want = set(words) | set(alias_tokens(words))
    ids = [rowid for rowid, _ in hits]
    rows = {
        r["rowid"]: r
        for r in conn.execute(
            f"SELECT rowid, product_id, title, brand, category, images, head, n_shops, min_price, median_price "
            f"FROM products WHERE rowid IN ({','.join('?' * len(ids))})",
            ids,
        )
    }
    items = []
    for rowid, rank in hits:
        r = rows[rowid]
        cat_toks = tokens(r["category"])
        cat_head = cat_toks[0] if cat_toks else None
        # boost only a product-type head word (it also names the category), not a brand or model word
        head_is_type = r["head"] in want and r["head"] in cat_toks
        score = -rank + (HEAD_BOOST if head_is_type else 0.0) + POPULARITY_WEIGHT * math.log1p(r["n_shops"])
        if any(h in ACCESSORY_HEADS and h not in want for h in (r["head"], cat_head)):
            score -= ACCESSORY_PENALTY
        item = dict(r)
        item["images"] = json.loads(item["images"])
        item["score"] = round(score, 3)
        item.pop("rowid")
        items.append(item)
    items.sort(key=lambda x: -x["score"])
    return {"words": words, "mode": mode, "total": len(hits), "items": items[:limit]}


def _fts(conn: sqlite3.Connection, expr: str) -> list[tuple[int, float]]:
    try:
        return conn.execute(
            "SELECT rowid, rank FROM products_fts WHERE products_fts MATCH ? ORDER BY rank LIMIT ?",
            (expr, CANDIDATES),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
