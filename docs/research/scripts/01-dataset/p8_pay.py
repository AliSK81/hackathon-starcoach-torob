from load import *
from collections import Counter
S=read("shops"); O=read("offers")
prov=Counter(); chan=Counter(); pc=Counter(); keys=Counter(); mm=Counter(); cats=Counter(); shopsprov=Counter(); combos=Counter()
ex=None
for s in S:
    po=J(s['payment_options']) or []
    if po and ex is None: ex=po
    combos[tuple(sorted({(p.get('provider_name'),p.get('channel')) for p in po}))]+=1 if po else 0
    for p in po:
        keys[tuple(sorted(p.keys()))]+=1
        prov[p.get('provider_name')]+=1; chan[p.get('channel')]+=1; pc[(p.get('provider_name'),p.get('channel'))]+=1
        mm[(p.get('provider_name'),p.get('min_price_toman'),p.get('max_price_toman'))]+=1
        cats[len(p.get('category_names') or [])]+=1
    for n in {p.get('provider_name') for p in po}: shopsprov[n]+=1
print("shops with non-empty payment_options:",sum(1 for s in S if J(s['payment_options'])))
print("example:",ex)
print("key sets:",keys); print("providers (entries):",prov); print("shops per provider:",shopsprov)
print("channels:",chan); print("provider x channel:",pc)
print("provider,min,max:",mm.most_common(20))
print("len(category_names) in payment entries:",sorted(cats.items()))
print("provider/channel combos per shop:",combos.most_common(10))
print("supports_fast_delivery:",Counter(s['supports_fast_delivery'] for s in S))
has_off={o['shop_id'] for o in O}
print("fast_delivery true & has offers:",sum(1 for s in S if s['supports_fast_delivery']=='true' and s['shop_id'] in has_off))
print("payment_options non-empty & has offers:",sum(1 for s in S if J(s['payment_options']) and s['shop_id'] in has_off))
# kalabarg search
import re
for col in ['address','category_names','payment_options','name']:
    print("kalabarg/کالابرگ in shops."+col,sum(1 for s in S if re.search('کالابرگ|kalabarg|بن کارت|کالا برگ',s[col],re.I)))
print("kalabarg in offers.description:",sum(1 for o in O if re.search('کالابرگ|کالا برگ',o['description'])),"seller_title:",sum(1 for o in O if re.search('کالابرگ|کالا برگ',o['seller_title'])))
print("ترب پی mention in descriptions:",sum(1 for o in O if re.search('ترب ?‌?پی|اقساط|قسطی',o['description'])))
# contacts
ch=Counter(); nums=Counter()
for s in S:
    c=J(s['contacts']) or []
    nums[len(c)]+=1
    for x in c: ch[(x.get('channel'),tuple(sorted(x.keys())))]+=1
print("contacts channels:",ch,"per shop count:",nums)
print("instagram examples:",[s['instagram'] for s in S if s['instagram']!='null'][:3],"website examples:",[s['website_url'] for s in S if s['website_url']!='null'][:3])
print("instagram or website:",sum(1 for s in S if s['instagram']!='null' or s['website_url']!='null'),"both:",sum(1 for s in S if s['instagram']!='null' and s['website_url']!='null'))
