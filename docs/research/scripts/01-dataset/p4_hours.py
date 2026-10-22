from load import *
from collections import Counter
S=read("shops")
W=[J(s['weekly_hours']) for s in S]
print("weekly_hours empty {}:",sum(1 for w in W if not w))
DAYS=["sat","sun","mon","tue","wed","thu","fri"]
keys=Counter(tuple(sorted(w.keys())) for w in W if w); print("day-key sets:",keys.most_common(3))
st=Counter(); nshift=Counter(); overnight=0; z=Counter(); fmt=Counter(); ex_over=[]
closed_with_nonzero=0; declared_zero=0; unsup_shifts=Counter(); full=0
per_shop_status=Counter()
for s,w in zip(S,W):
    if not w: continue
    per_shop_status[tuple(sorted(set(w[d]['status'] for d in w)))]+=1
    for d,v in w.items():
        st[(v['status'])]+=1
        sh=v.get('shifts') or []
        nshift[(v['status'],len(sh))]+=1
        for x in sh:
            fmt[(len(x['start_time']),len(x['end_time']))]+=1
            a,b=x['start_time'],x['end_time']
            if a=="00:00:00" and b=="00:00:00": z[v['status']]+=1
            elif b<=a and b!="00:00:00": overnight+=1; ex_over.append((s['shop_id'],d,a,b))
            elif b=="00:00:00" and a!="00:00:00": z['end_midnight_'+v['status']]+=1
            if v['status']=='declared' and a=="00:00:00" and b in("23:59:00","23:59:59","00:00:00"): full+=1
        if v['status']=='unsupported': unsup_shifts[str(sh)[:80]]+=1
print("day status counts:",st)
print("(status,#shifts):",sorted(nshift.items()))
print("time string lengths:",fmt)
print("00:00-00:00 by status / end at midnight:",z)
print("overnight shifts (end<start, end!=00:00):",overnight, ex_over[:5])
print("declared 00:00->23:59/00:00 (24h?):",full)
print("unsupported shift contents:",unsup_shifts.most_common(5))
print("per-shop status combos:",per_shop_status.most_common(10))
# common schedules
starts=Counter(); ends=Counter()
for w in W:
    if not w: continue
    for d,v in w.items():
        if v['status']=='declared':
            for x in v['shifts']: starts[x['start_time'][:5]]+=1; ends[x['end_time'][:5]]+=1
print("top starts",starts.most_common(8)); print("top ends",ends.most_common(8))
# friday
print("friday status:",Counter(w['fri']['status'] for w in W if w and 'fri' in w))
print("thursday status:",Counter(w['thu']['status'] for w in W if w and 'thu' in w))
# multi-shift example
for s,w in zip(S,W):
    if w and any(len(w[d]['shifts'])>1 for d in w):
        print("multi-shift example:",{d:(w[d]['status'],[(x['start_time'][:5],x['end_time'][:5]) for x in w[d]['shifts']]) for d in DAYS}); break
for s,w in zip(S,W):
    if w and any(w[d]['status']=='unsupported' for d in w):
        print("unsupported example:",{d:(w[d]['status'],[(x['start_time'][:5],x['end_time'][:5]) for x in w[d]['shifts']]) for d in DAYS}); break
shops_with_declared=sum(1 for w in W if w and any(w[d]['status']=='declared' for d in w))
print("shops with >=1 declared day:",shops_with_declared)
# shops with offers & hours
O=read("offers"); has_off={o['shop_id'] for o in O}
print("shops with offers:",len(has_off),"of which have >=1 declared day:",sum(1 for s,w in zip(S,W) if s['shop_id'] in has_off and w and any(w[d]['status']=='declared' for d in w)))
