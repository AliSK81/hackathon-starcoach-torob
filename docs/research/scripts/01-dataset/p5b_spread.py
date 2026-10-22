from load import *
from collections import Counter, defaultdict
import statistics, random
P=read("products"); O=read("offers")
pt={p['product_id']:p for p in P}
random.seed(3)
def band(lo,hi,k=6):
    xs=[o for o in O if o['price_toman']!='null' and lo<=float(o['price_toman'])<hi]
    print(f"[{lo:g},{hi:g}) n={len(xs)}")
    for o in random.sample(xs,min(k,len(xs))): print(f"   {float(o['price_toman']):,.0f} | {pt[o['product_id']]['category_name']} | {o['seller_title'][:60]}")
band(1e9,1e10); band(1e10,1e12); band(1e12,1e15); band(2,1000)
# spread per product among distinct shops (min price per shop)
g=defaultdict(dict)
for o in O:
    if o['price_toman']=='null': continue
    x=float(o['price_toman'])
    if not (1000<=x<=1e10): continue
    s=o['shop_id']; g[o['product_id']][s]=min(x,g[o['product_id']].get(s,1e30))
multi={p:list(v.values()) for p,v in g.items() if len(v)>=2}
print("products with >=2 shops priced (1e3..1e10):",len(multi), ">=3:",sum(len(v)>=3 for v in multi.values()), ">=5:",sum(len(v)>=5 for v in multi.values()))
r=sorted(max(v)/min(v) for v in multi.values())
n=len(r); print("max/min ratio: p25 %.2f median %.2f p75 %.2f p90 %.2f p99 %.1f"%(r[n//4],r[n//2],r[3*n//4],r[9*n//10],r[99*n//100]))
print("ratio==1 (identical prices):",sum(x==1 for x in r),"ratio>2:",sum(x>2 for x in r),"ratio>10:",sum(x>10 for x in r))
# outlier rule vs median for products with >=3 shops
out=0; tot=0
for v in multi.values():
    if len(v)<3: continue
    m=statistics.median(v)
    for x in v:
        tot+=1
        if x<m/3 or x>m*3: out+=1
print("offers (>=3 shops) outside [median/3, 3*median]:",out,"/",tot)
