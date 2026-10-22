from load import *
from collections import Counter
S=read("shops"); W=[J(s['weekly_hours']) for s in S]; Z="00:00:00"
c24=Counter(); c0=Counter(); dup=0
for w in W:
    if not w: continue
    for v in w.values():
        if v['status']!='declared': continue
        sh=[x for x in v['shifts'] if not(x['start_time']==Z and x['end_time']==Z)]
        if len(sh)==2 and sh[0]==sh[1]: dup+=1
        for x in sh:
            a,b=x['start_time'],x['end_time']; m=(int(b[:2])*60+int(b[3:5])-int(a[:2])*60-int(a[3:5]))
            if m>=23.5*60: c24[(a,b)]+=1
            if m<30: c0[(a,b)]+=1
print("~24h shifts:",c24.most_common(5)); print("<30min shifts:",c0.most_common(8)); print("2 identical shifts in a day:",dup)
