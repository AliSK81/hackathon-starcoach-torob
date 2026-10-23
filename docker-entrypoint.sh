#!/bin/sh
# Get the DB ready before the server starts:
#   1. DB already on the volume -> use it.
#   2. /seed/starcoach.db.gz in the image (first deploy on a host without a download link) -> unpack it.
#   3. DB_URL set -> download the packed DB (.gz) and check its SHA256 if DB_SHA256 is set.
#   4. CSVs on the volume -> build the DB.
# Otherwise the server still starts; /ready answers 503 until a DB exists.
set -e

if [ ! -f "$STARCOACH_DB" ] && [ -f /seed/starcoach.db.gz ]; then
  echo "unpacking seed DB"
  python -c "import gzip,os,shutil;d=os.environ['STARCOACH_DB'];shutil.copyfileobj(gzip.open('/seed/starcoach.db.gz','rb'),open(d+'.building','wb'));os.replace(d+'.building',d)"
fi

if [ ! -f "$STARCOACH_DB" ] && [ -n "$DB_URL" ]; then
  echo "downloading DB from DB_URL"
  python - <<'PY'
import gzip, hashlib, os, shutil, urllib.request
url, dest, want = os.environ["DB_URL"], os.environ["STARCOACH_DB"], os.environ.get("DB_SHA256", "")
tmp = dest + ".download"
urllib.request.urlretrieve(url, tmp)
if want:
    got = hashlib.sha256(open(tmp, "rb").read()).hexdigest()
    if got != want:
        os.remove(tmp)
        raise SystemExit(f"DB checksum mismatch: {got}")
with gzip.open(tmp, "rb") as src, open(dest + ".building", "wb") as out:
    shutil.copyfileobj(src, out)
os.replace(dest + ".building", dest)
os.remove(tmp)
print("DB ready")
PY
fi

if [ ! -f "$STARCOACH_DB" ] && [ -f "$STARCOACH_DATA_DIR/offers.csv" ]; then
  echo "building DB from $STARCOACH_DATA_DIR"
  starcoach build-db
fi

exec "$@"
