from load import *
from collections import Counter
S=read("shops"); W=[J(s['weekly_hours']) for s in S]
Z="00:00:00"
real=Counter(); onlyzero=0; over=[]; eq=[]; ends_mid=0; split=Counter(); shopsonlyzero=set(); dur=Counter()
for s,w in zip(S,W):
    if not w: continue
    for d,v in w.items():
        if v['status']!='declared': 
            if v['status']=='closed' and any(x['start_time']!=Z or x['end_time']!=Z for x in v['shifts']): real['closed_with_real_times']+=1
            continue
        sh=[x for x in v['shifts'] if not(x['start_time']==Z and x['end_time']==Z)]
        real[len(sh)]+=1
        if not sh: onlyzero+=1; shopsonlyzero.add(s['shop_id'])
        for x in sh:
            a,b=x['start_time'],x['end_time']
            if b==Z: ends_mid+=1
            elif b<a: over.append((a,b))
            elif a==b: eq.append(a)
            h=(int(b[:2])*60+int(b[3:5])-int(a[:2])*60-int(a[3:5]))%1440/60
            dur[round(h)]+=1
        if len(sh)==2: split[tuple((x['start_time'][:5],x['end_time'][:5]) for x in sh)]+=1
print("declared days by # real (non 00:00-00:00) shifts:",real)
print("declared days whose only shifts are 00:00-00:00:",onlyzero,"in shops:",len(shopsonlyzero))
print("real shifts ending at 00:00 (midnight close):",ends_mid)
print("overnight end<start:",len(over),Counter(over).most_common(5))
print("start==end non-zero (declared):",len(eq),Counter(eq).most_common(3))
print("shift duration hours:",sorted(dur.items()))
print("top split-shift patterns:",split.most_common(6))
# shops whose every declared day is only-zero
allzero=sum(1 for w in W if w and all((v['status']!='declared') or all(x['start_time']==Z and x['end_time']==Z for x in v['shifts']) for v in w.values()) and any(v['status']=='declared' for v in w.values()))
print("shops whose ALL declared days are 00:00-00:00 only:",allzero)
