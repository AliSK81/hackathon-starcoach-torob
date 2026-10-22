from load import *
from addr import parse, norm
from collections import Counter, defaultdict
import math, statistics, re
S=read("shops")
def hav(a,b,c,d):
    R=6371000; p1,p2=math.radians(a),math.radians(c); dp=p2-p1; dl=math.radians(d-b)
    h=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2; return 2*R*math.asin(math.sqrt(h))
lat=[float(s['lat']) for s in S]; lon=[float(s['lon']) for s in S]
print("lat range",min(lat),max(lat),"lon range",min(lon),max(lon))
print("outside Tehran bbox (35.55-35.85, 51.1-51.65):",sum(1 for a,b in zip(lat,lon) if not(35.55<=a<=35.85 and 51.1<=b<=51.65)))
print("lat decimals distribution (len of fractional part):",Counter(len(s['lat'].split('.')[1]) if '.' in s['lat'] else 0 for s in S).most_common(6))
co=Counter((s['lat'],s['lon']) for s in S)
shared=[c for c in co.values() if c>1]
print("distinct coords",len(co),"coords shared by >1 shop:",len(shared),"shops at shared coords:",sum(shared),"max shops at one coord:",max(co.values()))
for (a,b),c in co.most_common(8):
    ex=[s for s in S if s['lat']==a and s['lon']==b]
    print(f"  {c} @ {a[:9]},{b[:9]} label={Counter(e['location_label'] for e in ex).most_common(2)} addr_ex={ex[0]['address'][:70]}")
# rounded to 4 decimals (~11m)
co4=Counter((round(x,4),round(y,4)) for x,y in zip(lat,lon))
print("clusters at 4dp (~11m): distinct",len(co4),"with >=5 shops:",sum(1 for v in co4.values() if v>=5),"shops in them:",sum(v for v in co4.values() if v>=5))
# label stats
L=defaultdict(list)
for s,a,b in zip(S,lat,lon): L[s['location_label']].append((a,b))
print("\nlocation_label | n | centroid | median dist to centroid m | p95 m | max m")
for k,v in sorted(L.items(),key=lambda x:-len(x[1])):
    ca=statistics.mean(x for x,_ in v); cb=statistics.mean(y for _,y in v)
    d=sorted(hav(ca,cb,x,y) for x,y in v)
    print(f"{k or '<empty>'} | {len(v)} | {ca:.5f},{cb:.5f} | {statistics.median(d):.0f} | {d[int(.95*(len(d)-1))]:.0f} | {d[-1]:.0f}")
# global centroid of the downtown cluster
core=[(a,b) for s,a,b in zip(S,lat,lon) if s['location_label'] in ('فردوسی','شیخ هادی','بهارستان')]
ca=statistics.mean(x for x,_ in core); cb=statistics.mean(y for _,y in core)
dd=sorted(hav(ca,cb,a,b) for a,b in zip(lat,lon))
print("\ndist of all shops to downtown centroid",round(ca,5),round(cb,5),": within 500m",sum(d<=500 for d in dd),"1km",sum(d<=1000 for d in dd),"2km",sum(d<=2000 for d in dd),"5km",sum(d<=5000 for d in dd),"max",round(dd[-1]))
# does label match address text?
m=sum(1 for s in S if s['location_label'] and s['location_label'] in norm(s['address']))
print("label substring of address:",m)
# passage coordinate coherence: same canonical passage -> spread
def canon(x):
    x=re.sub(r"علا\S*دین","علاءالدین",x); return x.strip()
G=defaultdict(list)
for s,a,b in zip(S,lat,lon):
    p=parse(s['address'])['passage']
    if p: G[canon(p)].append((a,b,s['location_label']))
print("\npassage | n | distinct coords | median m to centroid | max m | labels")
for k,v in sorted(G.items(),key=lambda x:-len(x[1]))[:12]:
    ca=statistics.mean(x for x,_,_ in v); cb=statistics.mean(y for _,y,_ in v)
    d=sorted(hav(ca,cb,x,y) for x,y,_ in v)
    print(f"{k} | {len(v)} | {len(set((x,y) for x,y,_ in v))} | {statistics.median(d):.0f} | {d[-1]:.0f} | {Counter(l for *_,l in v).most_common(3)}")
