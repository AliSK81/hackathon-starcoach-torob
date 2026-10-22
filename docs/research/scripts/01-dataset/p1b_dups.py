from load import *
from collections import Counter, defaultdict
import statistics
S=read("shops"); P=read("products"); O=read("offers")
g=defaultdict(list)
for o in O: g[(o['shop_id'],o['product_id'])].append(o)
d=[v for v in g.values() if len(v)>1]
print("dup groups",len(d),"max group size",max(len(v) for v in d))
same_price=sum(1 for v in d if len({o['price_toman'] for o in v})==1)
same_title=sum(1 for v in d if len({o['seller_title'] for o in v})==1)
print("dup groups with identical price",same_price,"identical seller_title",same_title)
for v in sorted(d,key=len,reverse=True)[:1]+d[:3]:
    print("---")
    for o in v[:6]: print("  ",o['price_toman'],o['last_price_changed_at'][:19],o['seller_title'][:70])
# distinct shops per product
sp=defaultdict(set)
for o in O: sp[o['product_id']].add(o['shop_id'])
v=sorted(len(x) for x in sp.values())
print("distinct shops/product: median",statistics.median(v),"max",v[-1])
for lo,hi in [(1,1),(2,2),(3,5),(6,10),(11,20),(21,10**9)]:
    print(f"  {lo}-{hi}: {sum(lo<=x<=hi for x in v)}")
print("offers on products with >=2 distinct shops:", sum(len(g2) for g2 in [[o for o in O if len(sp[o['product_id']])>=2]]))
pt={r['product_id']:(r['persian_title'],r['category_name']) for r in P}
for p,s in sorted(sp.items(),key=lambda x:-len(x[1]))[:10]: print(" ",len(s),pt[p])
# shops with >300 offers: distinct products
ops=Counter(o['shop_id'] for o in O)
