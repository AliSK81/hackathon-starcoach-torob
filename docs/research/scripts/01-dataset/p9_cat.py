from load import *
from collections import Counter, defaultdict
P=read("products"); O=read("offers"); S=read("shops")
pcat={p['product_id']:p['category_name'] for p in P}
shopcats=Counter(); 
for s in S:
    for c in J(s['category_names']) or []: shopcats[c]+=1
prodcats=set(pcat.values())
print("distinct shop category_names:",len(shopcats),"distinct product category_name:",len(prodcats),"intersection:",len(set(shopcats)&prodcats))
print("shop cats not in product cats (top):",[(c,n) for c,n in shopcats.most_common() if c not in prodcats][:10])
lens=sorted(len(J(s['category_names']) or []) for s in S); print("cats per shop: median",lens[len(lens)//2],"max",lens[-1],"zero",lens.count(0))
# for shops with offers: fraction of their offer categories listed in their category_names
cover=[];inv=[]
offcats=defaultdict(Counter)
for o in O: offcats[o['shop_id']][pcat[o['product_id']]]+=1
for s in S:
    sc=set(J(s['category_names']) or [])
    oc=offcats.get(s['shop_id'])
    if not oc or not sc: continue
    cover.append(sum(v for c,v in oc.items() if c in sc)/sum(oc.values()))
cover.sort(); print("shops with both: ",len(cover),"share of offers whose category is in shop.category_names: median %.2f p25 %.2f"%(cover[len(cover)//2],cover[len(cover)//4]))
print("shops with category_names but no offers:",sum(1 for s in S if J(s['category_names']) and s['shop_id'] not in offcats),"; with offers but no category_names:",sum(1 for s in S if not J(s['category_names']) and s['shop_id'] in offcats), "; neither:",sum(1 for s in S if not J(s['category_names']) and s['shop_id'] not in offcats))
oc=Counter(pcat[o['product_id']] for o in O)
print("\ntop 30 product categories by offers (offers | products | shops):")
cs=defaultdict(set); cp=defaultdict(set)
for o in O: c=pcat[o['product_id']]; cs[c].add(o['shop_id']); cp[c].add(o['product_id'])
for c,n in oc.most_common(30): print(f"  {c} | {n} | {len(cp[c])} | {len(cs[c])}")
print("top shop category_names:",shopcats.most_common(15))
