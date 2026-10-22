from datetime import datetime
from zoneinfo import ZoneInfo
import sys
try:
    import tzdata; print("tzdata version", tzdata.IANA_VERSION)
except Exception as e: print("tzdata pkg:",e)
z=ZoneInfo("Asia/Tehran")
for d in ["2021-07-01","2022-07-01","2022-12-01","2023-07-01","2026-07-01","2026-10-22"]:
    t=datetime.fromisoformat(d+"T12:00").replace(tzinfo=z); print(d, t.utcoffset(), t.dst())
