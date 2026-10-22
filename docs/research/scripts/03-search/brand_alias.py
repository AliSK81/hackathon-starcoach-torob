"""Mine Persian<->Latin brand aliases from products.csv (brand_name + specs 'برند'/'شرکت سازنده'/'نام محصول' + title)."""
import csv, json, re, sys, os, collections, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fanorm import normalize
csv.field_size_limit(10**9)
SRC = r"D:\hackathon\hackathon-starcoach-torob\data\torob-dataset\products.csv"
LAT = re.compile(r"[a-z][a-z0-9\-&+.]{1,}")
GENERIC = {"pro", "max", "plus", "mini", "ultra", "lite", "new", "model", "series", "original", "smart", "usb", "led",
           "type", "gb", "tb", "mah", "mm", "cm", "w", "v", "hd", "full", "black", "white", "a", "s", "x", "the"}
t = time.perf_counter()
co = collections.defaultdict(collections.Counter); n_brand = collections.Counter()
for r in csv.DictReader(open(SRC, encoding="utf-8", newline="")):
    b = r["brand_name"]
    if b in ("", "null"): continue
    bf = normalize(b); n_brand[bf] += 1
    lat = set()
    try: specs = json.loads(r["specs"])
    except Exception: specs = []
    for d in specs if isinstance(specs, list) else []:
        if isinstance(d, dict) and d.get("key") in ("برند", "شرکت سازنده", "نام محصول"):
            toks = LAT.findall(normalize(str(d.get("value", ""))))
            if d.get("key") == "نام محصول": toks = toks[:1]           # first latin word of product name = brand
            lat.update(toks)
    tl = LAT.findall(normalize(r["persian_title"], split_alnum=False))
    lat.update(tl[:1])
    for l in lat - GENERIC: co[bf][l] += 1
# crude first-sound check: Persian first letter -> plausible Latin first letters
FIRST = {"ا": "aeiouh", "ب": "bp", "پ": "p", "ت": "t", "ث": "s", "ج": "jg", "چ": "c", "ح": "h", "خ": "kh", "د": "d",
         "ذ": "z", "ر": "r", "ز": "zx", "ژ": "jg", "س": "sc", "ش": "s", "ص": "s", "ض": "z", "ط": "t", "ظ": "z",
         "ع": "aeiou", "غ": "g", "ف": "fpv", "ق": "gq", "ک": "kcq", "گ": "g", "ل": "l", "م": "m", "ن": "n",
         "و": "vwou", "ه": "h", "ی": "iyej"}
aliases = {}
for bf, cnt in co.items():
    for l, c in cnt.most_common(8):
        if any(ch.isdigit() for ch in l): continue
        if l[0] not in FIRST.get(bf[0], ""): continue
        if c >= 5 and c / n_brand[bf] >= 0.05: aliases.setdefault(bf, []).append((l, c, n_brand[bf]))
print(f"{len(n_brand)} Persian brands, {len(aliases)} with a mined Latin alias, {time.perf_counter()-t:.1f}s")
for bf in sorted(aliases, key=lambda k: -n_brand[k])[:45]:
    print(f"  {bf:18} -> {aliases[bf]}")
json.dump(aliases, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "brand_aliases.json"), "w", encoding="utf-8"), ensure_ascii=False)
