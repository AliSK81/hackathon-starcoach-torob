import csv, json, sys, collections
csv.field_size_limit(10**9)
D = sys.argv[1]
def rows(f): return csv.DictReader(open(f"{D}/{f}", encoding='utf-8'))
C = collections.Counter
pay=C(); fast=C(); loc=C(); hours_status=C(); chan=C(); nullc=C(); cats=C(); n=0; empty_hours=0
for r in rows('shops.csv'):
    n+=1
    for k,v in r.items():
        if v in ('null','','[]','{}'): nullc[k]+=1
    for p in json.loads(r['payment_options'] or '[]'): pay[json.dumps(p,ensure_ascii=False)[:120]]+=1
    fast[r['supports_fast_delivery']]+=1
    loc[r['location_label']]+=1
    wh=json.loads(r['weekly_hours'] or '{}')
    if not wh: empty_hours+=1
    for d,v in wh.items(): hours_status[v.get('status')]+=1
    for c in json.loads(r['contacts'] or '[]'): chan[c.get('channel')]+=1
    for c in json.loads(r['category_names'] or '[]'): cats[c]+=1
print('shops',n,'empty_hours',empty_hours)
print('nulls',nullc)
print('pay',pay.most_common(20))
print('fast',fast)
print('hours_status',hours_status)
print('channels',chan)
print('loc top',loc.most_common(40), 'n_loc',len(loc))
print('cats top',cats.most_common(30),'n_cats',len(cats))
# products
nullp=C(); pc=C(); brands=C(); n=0; seckeys=C()
for r in rows('products.csv'):
    n+=1
    for k,v in r.items():
        if v in ('null','','[]','{}'): nullp[k]+=1
    pc[r['category_name']]+=1; brands[r['brand_name']]+=1
print('products',n,'nulls',nullp)
print('pcats',pc.most_common(30),'n',len(pc))
print('brands',brands.most_common(20),'n',len(brands))
# offers
nullo=C(); war=C(); n=0; dates=[]; prices=[]; per_prod=C(); desc_len=0
for r in rows('offers.csv'):
    n+=1
    for k,v in r.items():
        if v in ('null','','[]','{}'): nullo[k]+=1
    war[r['warranty'][:80]]+=1
    dates.append(r['last_price_changed_at'][:10]); per_prod[r['product_id']]+=1
    try: prices.append(int(float(r['price_toman'])))
    except: nullo['badprice']+=1
print('offers',n,'nulls',nullo)
print('warranty',war.most_common(15))
dc=C(dates); print('dates',sorted(dc.items())[:5], sorted(dc.items())[-5:], 'n',len(dc))
prices.sort(); print('price min/med/max',prices[0],prices[len(prices)//2],prices[-1], 'zeros',sum(1 for p in prices if p==0))
ppc=C(per_prod.values()); print('offers per product',sorted(ppc.items())[:10], 'max',max(per_prod.values()))
