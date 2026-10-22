import csv, os, re, sqlite3, sys, time, difflib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fanorm import normalize
csv.field_size_limit(10**9)
OUT = os.path.dirname(os.path.abspath(__file__))
OFFERS = r"D:\hackathon\hackathon-starcoach-torob\data\torob-dataset\offers.csv"
uni = sqlite3.connect(os.path.join(OUT, "uni.db"))

# ---- 1. vocabulary + typo correction via trigram index over vocab ----
t = time.perf_counter()
uni.execute("CREATE VIRTUAL TABLE IF NOT EXISTS temp.v USING fts5vocab(main, p, row)")
vocab = uni.execute("SELECT term, doc FROM temp.v WHERE term NOT GLOB '*[0-9]*'").fetchall()
print(f"vocab terms (non-numeric): {len(vocab)} in {(time.perf_counter()-t)*1000:.0f} ms")
voc = sqlite3.connect(":memory:")
voc.execute("CREATE VIRTUAL TABLE vt USING fts5(term, tokenize='trigram')")
voc.execute("CREATE TABLE df(term TEXT PRIMARY KEY, doc INT)")
voc.executemany("INSERT INTO vt VALUES (?)", [(v[0],) for v in vocab])
voc.executemany("INSERT INTO df VALUES (?,?)", vocab)
DF = dict(vocab)

def trigrams(s):
    s = f" {s} "
    return {s[i:i+3] for i in range(len(s) - 2)}

def correct(tok, k=3):
    """Return best vocab candidates for an unknown token: candidates share >=1 trigram (OR query), scored by
    trigram Jaccard * log(df)."""
    if tok in DF: return [(tok, 1.0)]
    grams = [g for g in trigrams(tok) if " " not in g]
    if not grams: return []
    expr = " OR ".join('"%s"' % g for g in grams)
    cands = voc.execute("SELECT term FROM vt WHERE vt MATCH ? LIMIT 2000", (expr,)).fetchall()
    tg = trigrams(tok); out = []
    import math
    for (c,) in cands:
        if abs(len(c) - len(tok)) > 2: continue
        j = len(tg & trigrams(c)) / len(tg | trigrams(c))
        r = difflib.SequenceMatcher(None, tok, c).ratio()
        out.append((c, round((j + r) / 2 * (1 + 0.05 * math.log1p(DF[c])), 3)))
    return sorted(out, key=lambda x: -x[1])[:k]

for typo in ["سامسنگ", "شیامی", "هندزفیری", "بلوتوت", "ایفن", "کاسیوو", "یخچل", "هدفن"]:
    t = time.perf_counter(); c = correct(normalize(typo)); dt = (time.perf_counter()-t)*1000
    print(f"correct({typo}) -> {c}  [{dt:.1f} ms]")

# ---- 2. alias expansion + category-aware ranking ----
ALIAS = {"ایفون": ["iphone"], "iphone": ["ایفون"], "سامسونگ": ["samsung"], "samsung": ["سامسونگ"],
         "شیامی": ["شیائومی", "xiaomi"], "شیائومی": ["xiaomi"], "xiaomi": ["شیائومی"], "اپل": ["apple"], "apple": ["اپل"]}
def expr_for(tokens):
    parts = []
    for i, t in enumerate(tokens):
        alts = [t] + ALIAS.get(t, [])
        star = "*" if i == len(tokens) - 1 else ""
        parts.append("(" + " OR ".join(f'"{a}"{star}' for a in alts) + ")")
    return " AND ".join(parts)

for q in ["آیفون ۱۳ ۱۲۸", "شیامی ردمی", "گوشی سامسونگ"]:
    e = expr_for(normalize(q).split())
    t = time.perf_counter()
    res = uni.execute("SELECT raw, category FROM p WHERE p MATCH ? ORDER BY bm25(p,5.0,3.0,1.0) LIMIT 3", (e,)).fetchall()
    n = uni.execute("SELECT count(*) FROM p WHERE p MATCH ?", (e,)).fetchone()[0]
    print(f"\n{q} => {e}: {n} hits {(time.perf_counter()-t)*1000:.1f} ms")
    for r in res: print("   -", r)
    # category boost: categories whose name matches the query head noun get a bonus
    t = time.perf_counter()
    res = uni.execute("""SELECT raw, category, bm25(p,5.0,3.0,1.0) - (CASE WHEN category LIKE '%گوشی موبایل%' THEN 5 ELSE 0 END) s
                         FROM p WHERE p MATCH ? ORDER BY s LIMIT 3""", (e,)).fetchall()
    print(f"  with category boost ('گوشی موبایل'): {(time.perf_counter()-t)*1000:.1f} ms")
    for r in res: print("   -", r[:2])

# ---- 3. seller-title index (offers.csv, 331k) ----
t = time.perf_counter()
rows = []
with open(OFFERS, encoding="utf-8", newline="") as f:
    for r in csv.DictReader(f):
        rows.append((r["offer_id"], r["product_id"], normalize(r["seller_title"])))
tn = time.perf_counter() - t
path = os.path.join(OUT, "offers_uni.db")
if os.path.exists(path): os.remove(path)
con = sqlite3.connect(path)
con.execute("CREATE VIRTUAL TABLE o USING fts5(offer_id UNINDEXED, product_id UNINDEXED, title, tokenize='unicode61 remove_diacritics 2', prefix='2 3', content='', contentless_unindexed=1)")
t = time.perf_counter()
con.executemany("INSERT INTO o VALUES (?,?,?)", rows); con.commit()
con.execute("INSERT INTO o(o) VALUES('optimize')"); con.commit()
tb = time.perf_counter() - t
con.execute("VACUUM"); con.close()
print(f"\noffers: {len(rows)} seller titles, read+normalize {tn:.1f}s, contentless FTS build {tb:.1f}s, size {os.path.getsize(path)/2**20:.1f} MiB")
con = sqlite3.connect(path)
for q in ["گوشی سامسونگ", "ایفون 13 128"]:
    e = " AND ".join('"%s"' % t for t in normalize(q).split())
    t = time.perf_counter()
    res = con.execute("SELECT product_id, count(*) c, min(bm25(o)) FROM o WHERE o MATCH ? GROUP BY product_id ORDER BY 3 LIMIT 5", (e,)).fetchall()
    print(f"  offers {q}: {(time.perf_counter()-t)*1000:.1f} ms, top product_ids {[r[0][-8:] for r in res]}")
