from load import *
from addr import parse
from collections import Counter, defaultdict
import statistics, re, math
S=read("shops"); O=read("offers")
pps=defaultdict(set)
for o in O: pps[o['shop_id']].add(o['product_id'])
print("shops with exactly 300 distinct products:",sum(1 for v in pps.values() if len(v)==300),"; >=250:",sum(1 for v in pps.values() if len(v)>=250))
# passage centroids (median) and pairwise distances
def canon(x): return re.sub(r"علا\S*دین","علاءالدین",x).strip() if x else None
G=defaultdict(list)
for s in S:
    p=canon(parse(s['address'])['passage'])
    if p: G[p].append((float(s['lat']),float(s['lon'])))
names=["علاءالدین","علاءالدین 2","چارسو","بوشهری","کیان","تجارت جهانی فردوسی","موبایل ایران","پلاسکو","اپال","کوروش"]
C={n:(statistics.median(x for x,_ in G[n]),statistics.median(y for _,y in G[n])) for n in names if n in G}
def hav(a,b):
    R=6371000; p1,p2=map(math.radians,(a[0],b[0])); dl=math.radians(b[1]-a[1]); dp=p2-p1
    return 2*R*math.asin(math.sqrt(math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2))
for n,c in C.items(): print(f"  {n}: n={len(G[n])} median={c[0]:.5f},{c[1]:.5f}")
base="علاءالدین"
for n in C: print(f"  dist {base} -> {n}: {hav(C[base],C[n]):.0f} m")
# completeness of shops WITH offers
has={o['shop_id'] for o in O}; SH=[s for s in S if s['shop_id'] in has]
def pct(f): c=sum(1 for s in SH if f(s)); return f"{c} ({100*c/len(SH):.0f}%)"
print("shops with offers:",len(SH))
print("  weekly_hours non-empty:",pct(lambda s:s['weekly_hours']!='{}'))
print("  payment_options non-empty:",pct(lambda s:s['payment_options']!='[]'))
print("  supports_fast_delivery not null:",pct(lambda s:s['supports_fast_delivery']!='null'))
print("  address has passage:",pct(lambda s:parse(s['address'])['passage'] is not None))
print("  address has floor:",pct(lambda s:parse(s['address'])['floor_raw'] is not None))
print("  instagram/website:",pct(lambda s:s['instagram']!='null' or s['website_url']!='null'))
print("phone display formats:",Counter(re.sub('[۰-۹]','d',json.loads(s['contacts'])[0]['display_number']) for s in S).most_common(4))
