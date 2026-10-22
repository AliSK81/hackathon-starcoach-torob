from load import *
from collections import Counter
from datetime import datetime, timedelta
O=read("offers")
ts=[]; fmts=Counter()
for o in O:
    v=o['last_price_changed_at']
    if v=='null': continue
    fmts[(len(v), v[-6:])]+=1
    ts.append(datetime.fromisoformat(v))
print("formats (len, tz suffix):",fmts.most_common(5))
ts.sort(); n=len(ts); newest=ts[-1]
print("count",n,"oldest",ts[0],"newest",newest,"median",ts[n//2])
for d in [1,3,7,14,30,90,180,365,730]:
    c=sum(1 for t in ts if t>=newest-timedelta(days=d)); print(f"  within {d}d of newest: {c} ({100*c/n:.1f}%)")
print("by year:",sorted(Counter(t.year for t in ts).items()))
print("2026 by month:",sorted(Counter(t.month for t in ts if t.year==2026).items()))
print("last 10 days by date:",sorted(Counter(t.date().isoformat() for t in ts if t>=newest-timedelta(days=10)).items()))
print("future vs today 2026-10-22:",sum(1 for t in ts if t.date().isoformat()>"2026-10-22"))
