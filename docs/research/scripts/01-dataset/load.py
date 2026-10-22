import csv, json, os, pickle, sys
csv.field_size_limit(10**9)
D = os.environ.get("TOROB_DATA", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "data", "torob-dataset"))
HERE = os.path.dirname(os.path.abspath(__file__))
def read(name):
    p = os.path.join(HERE, name + ".pkl")
    if os.path.exists(p):
        return pickle.load(open(p, "rb"))
    with open(os.path.join(D, name + ".csv"), encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    pickle.dump(rows, open(p, "wb"))
    return rows
def J(s):
    if s is None or s == "" or s == "null": return None
    try: return json.loads(s)
    except Exception: return s
