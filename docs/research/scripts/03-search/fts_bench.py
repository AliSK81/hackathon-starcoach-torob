import csv, os, re, sqlite3, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fanorm import normalize

csv.field_size_limit(10**9)
SRC = r"D:\hackathon\hackathon-starcoach-torob\data\torob-dataset\products.csv"
OUT = os.path.dirname(os.path.abspath(__file__))
print("sqlite", sqlite3.sqlite_version)

t0 = time.perf_counter()
rows = []
with open(SRC, encoding="utf-8", newline="") as f:
    for r in csv.DictReader(f):
        b = r["brand_name"] if r["brand_name"] != "null" else ""
        rows.append((r["product_id"], normalize(r["persian_title"]), normalize(b),
                     normalize(r["category_name"]), r["persian_title"]))
print(f"read+normalize {len(rows)} products: {time.perf_counter()-t0:.1f}s")

# raw-size baseline: plain table with same columns, no FTS
def plain():
    path = os.path.join(OUT, "plain.db")
    if os.path.exists(path): os.remove(path)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE p(product_id, title, brand, category, raw)")
    con.executemany("INSERT INTO p VALUES (?,?,?,?,?)", rows); con.commit(); con.execute("VACUUM"); con.close()
    print(f"[plain table, no index] size {os.path.getsize(path)/2**20:.1f} MiB")
plain()

def build(name, opts):
    path = os.path.join(OUT, f"{name}.db")
    if os.path.exists(path): os.remove(path)
    con = sqlite3.connect(path)
    con.execute(f"CREATE VIRTUAL TABLE p USING fts5(product_id UNINDEXED, title, brand, category, raw UNINDEXED, {opts})")
    t = time.perf_counter()
    con.executemany("INSERT INTO p VALUES (?,?,?,?,?)", rows); con.commit()
    con.execute("INSERT INTO p(p) VALUES('optimize')"); con.commit()
    dt = time.perf_counter() - t
    con.execute("VACUUM"); con.close()
    print(f"[{name}] {opts}: build {dt:.1f}s, size {os.path.getsize(path)/2**20:.1f} MiB")
    return sqlite3.connect(path)

uni = build("uni", "tokenize='unicode61 remove_diacritics 2', prefix='2 3'")
tri = build("tri", "tokenize='trigram'")

STOP = {"ها", "های", "مدل", "برای", "با", "و", "ارزون", "ارزان", "قیمت", "خرید", "بهترین"}

def terms(q):
    return [t for t in re.findall(r"\w+", normalize(q)) if t not in STOP]

def q_uni(q, mode="AND"):
    ts = terms(q)
    parts = ['"%s"' % t for t in ts[:-1]] + ['"%s"*' % ts[-1]]
    return f" {mode} ".join(parts)

def run_uni(q, k=3):
    for mode in ("AND", "OR"):
        expr = q_uni(q, mode)
        t = time.perf_counter()
        res = uni.execute("SELECT raw, bm25(p, 5.0, 3.0, 1.0) s FROM p WHERE p MATCH ? ORDER BY s LIMIT ?", (expr, k)).fetchall()
        n = uni.execute("SELECT count(*) FROM p WHERE p MATCH ?", (expr,)).fetchone()[0]
        dt = (time.perf_counter() - t) * 1000
        if res: return mode, expr, n, dt, res
    return mode, expr, 0, dt, []

def run_tri(q, k=3):
    ts = terms(q)
    long_ = [t for t in ts if len(t) >= 3]
    short = [t for t in ts if len(t) < 3]
    where, args = [], []
    if long_:
        where.append("p MATCH ?"); args.append(" AND ".join('title:"%s"' % t for t in long_))
    for s in short:  # trigram can't MATCH <3 chars: fall back to LIKE on the row (scan of candidate rows)
        where.append("title LIKE ?"); args.append(f"%{s}%")
    sql_w = " AND ".join(where)
    t = time.perf_counter()
    order = "ORDER BY bm25(p)" if long_ else ""
    res = tri.execute(f"SELECT raw FROM p WHERE {sql_w} {order} LIMIT {k}", args).fetchall()
    n = tri.execute(f"SELECT count(*) FROM p WHERE {sql_w}", args).fetchone()[0]
    dt = (time.perf_counter() - t) * 1000
    return sql_w, n, dt, res

QUERIES = ["گوشی سامسونگ", "آیفون ۱۳ ۱۲۸", "هندزفری بلوتوث ارزون", "iphone 13", "لنز دوربین سونی",
           "کابل افشان ۱۶×۵", "شیامی ردمی", "هدفون بی‌سیم", "samsung a54", "ساعت کاسیو", "ایرپاد", "سامسنگ"]

for q in QUERIES:
    mode, expr, n, dt, res = run_uni(q)
    print(f"\n### {q}\n unicode61 [{mode}] {expr!r}: {n} hits, {dt:.1f} ms")
    for r in res: print("   -", r[0])
    w, n2, dt2, res2 = run_tri(q)
    print(f" trigram: {n2} hits, {dt2:.1f} ms")
    for r in res2: print("   -", r[0])
