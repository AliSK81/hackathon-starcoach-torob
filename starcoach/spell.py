"""Typo correction for query words, from the search index's own vocabulary (research 03 §5.1).

Only words that are not in the vocabulary are corrected, and only when the query found nothing.
"""

import math
import sqlite3
from collections import defaultdict
from difflib import SequenceMatcher

MIN_LEN = 3
MAX_LEN_DIFF = 2
MIN_SCORE = 0.72
_cache: dict[str, tuple[dict[str, int], dict[str, list[str]]]] = {}


def _trigrams(word: str) -> set[str]:
    w = f"#{word}#"
    return {w[i : i + 3] for i in range(len(w) - 2)}


def vocabulary(conn: sqlite3.Connection, key: str) -> tuple[dict[str, int], dict[str, list[str]]]:
    """(term -> document count, trigram -> terms), built once per DB file."""
    if key not in _cache:
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS temp.sc_vocab USING fts5vocab(main, products_fts, row)")
        terms = {t: n for t, n in conn.execute("SELECT term, doc FROM temp.sc_vocab")
                 if len(t) >= MIN_LEN and not t.isdigit()}
        index: dict[str, list[str]] = defaultdict(list)
        for t in terms:
            for g in _trigrams(t):
                index[g].append(t)
        _cache[key] = (terms, dict(index))
    return _cache[key]


def correct(word: str, terms: dict[str, int], index: dict[str, list[str]]) -> str | None:
    """Best vocabulary word for an unknown `word`, or None."""
    if len(word) < MIN_LEN or word.isdigit() or word in terms:
        return None
    grams = _trigrams(word)
    counts: dict[str, int] = defaultdict(int)
    for g in grams:
        for t in index.get(g, ()):
            counts[t] += 1
    best, best_score = None, 0.0
    for t, shared in counts.items():
        if abs(len(t) - len(word)) > MAX_LEN_DIFF:
            continue
        jaccard = shared / len(grams | _trigrams(t))
        score = (jaccard + SequenceMatcher(None, word, t).ratio()) / 2 * (1 + 0.05 * math.log1p(terms[t]))
        if score > best_score:
            best, best_score = t, score
    return best if best_score >= MIN_SCORE else None
