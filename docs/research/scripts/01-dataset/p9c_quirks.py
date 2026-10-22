from load import *
from collections import Counter, defaultdict
import statistics
P=read("products"); O=read("offers")
red=[p for p in P if 'حذف' in p['persian_title'] and 'انتشار' in p['persian_title']]
print("redacted persian_title:",len(red),Counter(p['persian_title'] for p in red).most_common(3))
print("redacted seller_title:",sum(1 for o in O if 'حذف‌شده برای انتشار' in o['seller_title'] or 'حذف شده برای انتشار' in o['seller_title']))
rp={p['product_id'] for p in red}; print("offers on redacted products:",sum(1 for o in O if o['product_id'] in rp), "categories:",Counter(p['category_name'] for p in red).most_common(5))
tc=Counter(p['persian_title'] for p in P); d=[(t,c) for t,c in tc.items() if c>1]
print("persian_titles shared by >1 product_id:",len(d),"products involved:",sum(c for _,c in d)); print("  top:",sorted(d,key=lambda x:-x[1])[:5])
# ~10x outliers
g=defaultdict(dict)
for o in O:
    if o['price_toman']=='null': continue
    x=float(o['price_toman'])
    if 1000<=x<=1e10: g[o['product_id']][o['shop_id']]=min(x,g[o['product_id']].get(o['shop_id'],1e30))
ten=0; tot=0; tenth=0
for v in g.values():
    if len(v)<3: continue
    m=statistics.median(v.values())
    for x in v.values():
        tot+=1; r=x/m
        if 8<=r<=12: ten+=1
        if 1/12<=r<=1/8: tenth+=1
print(f"offers (products w/ >=3 shops) at 8-12x median: {ten}, at 1/12-1/8 of median: {tenth}, of {tot}")
