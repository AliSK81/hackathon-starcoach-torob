from load import *
from collections import Counter, defaultdict
import statistics, math
P=read("products"); O=read("offers"); S=read("shops")
pt={p['product_id']:p for p in P}
pr=[]; bad=Counter()
for o in O:
    v=o['price_toman']
    if v=='null': continue
    try: x=float(v)
    except: bad[v]+=1; continue
    pr.append(x)
print("non-null",len(pr),"null",sum(o['price_toman']=='null' for o in O),"unparseable",sum(bad.values()),bad.most_common(3))
print("non-integer values:",sum(1 for x in pr if x!=int(x)), "string with '.':",sum(1 for o in O if '.' in o['price_toman']))
pr.sort(); n=len(pr)
q=lambda f: pr[min(n-1,int(f*n))]
print("min",pr[0],"p1",q(.01),"p5",q(.05),"p25",q(.25),"median",q(.5),"p75",q(.75),"p95",q(.95),"p99",q(.99),"p99.9",q(.999),"max",pr[-1])
for t in [0,1,10,100,1000,10000,1e5]:
    print(f"  price<={t:g}: {sum(1 for x in pr if x<=t)}")
for t in [1e9,1e10,5e10,1e11,1e12,1e15]:
    print(f"  price>={t:g}: {sum(1 for x in pr if x>=t)}")
print("log10 histogram:",sorted(Counter(int(math.log10(x)) if x>0 else -1 for x in pr).items()))
# top values
print("top 12 prices with titles:")
big=sorted([o for o in O if o['price_toman']!='null'],key=lambda o:-float(o['price_toman']))[:12]
for o in big: print("  %.3g"%float(o['price_toman']), pt[o['product_id']]['category_name'],'|',o['seller_title'][:60])
print("lowest non-zero 8:")
small=sorted([o for o in O if o['price_toman']!='null' and float(o['price_toman'])>0],key=lambda o:float(o['price_toman']))[:8]
for o in small: print("  ",o['price_toman'], pt[o['product_id']]['category_name'],'|',o['seller_title'][:60])
# Common-sense check of Toman: iPhone / Apple 20W charger
def show(sub):
    xs=[float(o['price_toman']) for o in O if o['price_toman']!='null' and sub in pt[o['product_id']]['persian_title']]
    xs.sort(); 
    if xs: print(f"  '{sub}': n={len(xs)} median={statistics.median(xs):,.0f} min={xs[0]:,.0f} max={xs[-1]:,.0f}")
print("sanity products:")
for s in ["شارژر اپل توان 20 وات سه پین","آیفون 16 پرو","گوشی موبایل سامسونگ مدل Galaxy A56","گوشی موبایل سامسونگ مدل Galaxy S25 Ultra"]: show(s)
# null price meaning
nulls=[o for o in O if o['price_toman']=='null']
print("null-price: distinct shops",len({o['shop_id'] for o in nulls}),"top shops share",Counter(o['shop_id'] for o in nulls).most_common(5))
print("null-price with description:",sum(1 for o in nulls if o['description']),"; examples:",[o['description'][:60] for o in nulls if o['description']][:4])
print("null-price categories:",Counter(pt[o['product_id']]['category_name'] for o in nulls).most_common(8))
print("null-price last_price_changed_at null:",sum(o['last_price_changed_at']=='null' for o in nulls),"; overall null ts:",sum(o['last_price_changed_at']=='null' for o in O))
nts=[o for o in O if o['last_price_changed_at']=='null']; print("null-ts offers with null price:",sum(o['price_toman']=='null' for o in nts))
# shops whose all offers null
bys=defaultdict(list)
for o in O: bys[o['shop_id']].append(o['price_toman']=='null')
print("shops with all offers null-price:",sum(1 for v in bys.values() if all(v)),"; shops with some null:",sum(1 for v in bys.values() if any(v)))
# price zero
print("price==0:",sum(1 for x in pr if x==0))
