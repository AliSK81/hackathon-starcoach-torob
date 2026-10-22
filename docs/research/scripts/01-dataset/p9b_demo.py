from load import *
from addr import parse
from collections import Counter, defaultdict
import statistics, re
P=read("products"); O=read("offers"); S=read("shops")
pt={p['product_id']:p for p in P}; sh={s['shop_id']:s for s in S}
def canon(x):
    if not x: return None
    return re.sub(r"علا\S*دین","علاءالدین",x).strip()
spass={s['shop_id']:canon(parse(s['address'])['passage']) for s in S}
byp=defaultdict(list)
for o in O:
    if o['price_toman']=='null': continue
    x=float(o['price_toman'])
    if 1000<=x<=1e10: byp[o['product_id']].append(o)
def summarize(pid):
    os_=byp[pid]; shops={}
    for o in os_:
        x=float(o['price_toman']); s=o['shop_id']
        shops[s]=min(x,shops.get(s,1e30))
    v=sorted(shops.values())
    pas=Counter(spass[s] for s in shops if spass[s])
    lbl=Counter(sh[s]['location_label'] for s in shops)
    newest=max(o['last_price_changed_at'] for o in os_)
    return len(shops),v[0],statistics.median(v),v[-1],pas.most_common(3),lbl.most_common(3),newest[:10]
cats=["گوشی موبایل","شارژر گوشی","هدفون، هدست و هندزفری","دوربین مدار بسته","دزدگیر اماکن و لوازم جانبی","سیم و کابل برق ساختمان","اسپیکر و سیستم صوتی","ساعت هوشمند","پاور بانک (شارژر همراه)","لامپ","کابل شارژ","سیم سیار و چندراهی برق","مودم و روتر","هارد دیسک اکسترنال","فلش مموری","کیف و کاور گوشی","ساعت مچی عقربه‌ ای و دیجیتالی","تبلت","لپ تاپ و نوت بوک","کنسول بازی"]
allcats=Counter(p['category_name'] for p in P)
for c in cats:
    if c not in allcats: 
        print("## (no such category)",c, [k for k in allcats if c.split()[0] in k][:5]); continue
    pids=[p for p in byp if pt[p]['category_name']==c]
    top=sorted(pids,key=lambda p:-len({o['shop_id'] for o in byp[p]}))[:4]
    print("##",c,"| products w/ sane price:",len(pids))
    for p in top:
        n,mn,md,mx,pas,lbl,nw=summarize(p)
        print(f"   {pt[p]['persian_title'][:70]} | shops={n} min={mn:,.0f} med={md:,.0f} max={mx:,.0f} | {pas} | {lbl} | newest={nw}")
