from load import *
from collections import Counter
S=read("shops"); P=read("products"); O=read("offers")
print("== null/empty per column ==")
for name,R in [("shops",S),("products",P),("offers",O)]:
    for c in R[0]:
        vals=[r[c] for r in R]
        print(f"{name}.{c}: null={sum(v=='null' for v in vals)} empty={sum(v=='' for v in vals)} emptylist={sum(v=='[]' for v in vals)} emptyobj={sum(v=='{}' for v in vals)} distinct={len(set(vals))}")
sid={r['shop_id'] for r in S}; pid={r['product_id'] for r in P}
print("dup shop_id", len(S)-len(sid), "dup product_id", len(P)-len(pid), "dup offer_id", len(O)-len({o['offer_id'] for o in O}))
print("offers orphan product", sum(o['product_id'] not in pid for o in O))
print("offers orphan shop", sum(o['shop_id'] not in sid for o in O))
ops=Counter(o['shop_id'] for o in O)
print("shops with zero offers", sum(1 for s in sid if ops[s]==0))
print("products with zero offers", len(pid - {o['product_id'] for o in O}))
pairs=Counter((o['shop_id'],o['product_id']) for o in O)
print("dup (shop,product) pairs:", sum(1 for v in pairs.values() if v>1), "extra rows", sum(v-1 for v in pairs.values() if v>1))
vals=sorted(ops[s] for s in sid)
import statistics
print("offers/shop: min",vals[0],"median",statistics.median(vals),"mean",round(statistics.mean(vals),1),"max",vals[-1])
for lo,hi in [(0,0),(1,1),(2,5),(6,20),(21,50),(51,100),(101,200),(201,299),(300,300),(301,10**9)]:
    print(f"  {lo}-{hi}: {sum(lo<=v<=hi for v in vals)}")
pps=Counter(); 
for (s,p) in pairs: pps[s]+=1
print("max distinct products per shop", max(pps.values()))
spp=Counter(o['product_id'] for o in O)
v=sorted(spp.values())
print("offers/product: median",statistics.median(v),"max",v[-1])
for lo,hi in [(1,1),(2,2),(3,5),(6,10),(11,20),(21,10**9)]:
    print(f"  {lo}-{hi}: {sum(lo<=x<=hi for x in v)}")
top=spp.most_common(5); pt={r['product_id']:r['persian_title'] for r in P}
for p,c in top: print("  top", c, pt[p][:80])
