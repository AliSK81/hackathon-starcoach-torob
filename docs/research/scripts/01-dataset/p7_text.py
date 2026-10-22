from load import *
from collections import Counter, defaultdict
import re, difflib, random
P=read("products"); O=read("offers"); S=read("shops")
pt={p['product_id']:p for p in P}
def stats(name, xs):
    n=len(xs)
    f=lambda pat: sum(1 for x in xs if re.search(pat,x))
    print(f"{name} (n={n}): arabic_yeh/kaf {f('[يك]')}, persian ی/ک {f('[یک]')}, ZWNJ {f(chr(0x200c))}, fa-digits {f('[۰-۹]')}, ar-digits {f('[٠-٩]')}, latin-digits {f('[0-9]')}, mixed fa+latin digits {sum(1 for x in xs if re.search('[۰-۹]',x) and re.search('[0-9]',x))}, latin letters {f('[A-Za-z]')}, no Persian letters {sum(1 for x in xs if x and not re.search('[آ-ی]',x))}, ascii-only {sum(1 for x in xs if x and x.isascii())}")
stats("persian_title",[p['persian_title'] for p in P])
stats("seller_title",[o['seller_title'] for o in O])
stats("offer.description(non-empty)",[o['description'] for o in O if o['description']])
stats("shop.address",[s['address'] for s in S])
stats("shop.name",[s['name'] for s in S])
stats("specs values",[d['value'] for p in P[:50000] for d in (J(p['specs']) or [])])
# english titles
eng=[p['persian_title'] for p in P if p['persian_title'] and not re.search('[آ-ی]',p['persian_title'])]
print("ascii/latin-only persian_title examples:",eng[:5])
# seller_title vs persian_title
def nz(s): return re.sub(r"\s+"," ",s.replace("ي","ی").replace("ك","ک").replace("‌"," ")).strip()
same=0; contains=0; ratios=[]
random.seed(5); samp=random.sample(O,20000)
for o in samp:
    a=nz(o['seller_title']); b=nz(pt[o['product_id']]['persian_title'])
    if a==b: same+=1
    elif b in a or a in b: contains+=1
    ratios.append(difflib.SequenceMatcher(None,a,b).ratio())
ratios.sort(); n=len(ratios)
print(f"seller_title vs persian_title (20k sample): identical after norm {same}, substring {contains}, similarity median {ratios[n//2]:.2f} p10 {ratios[n//10]:.2f}")
print("seller_title length median",sorted(len(o['seller_title']) for o in O)[len(O)//2],"persian_title median",sorted(len(p['persian_title']) for p in P)[len(P)//2])
for o in random.sample(O,8): print("   S:",o['seller_title'][:80],"\n   P:",pt[o['product_id']]['persian_title'][:80])
# brand / model / category
print("brand null:",sum(p['brand_name']=='null' for p in P),"of",len(P),"; model null:",sum(p['model']=='null' for p in P),"; category null:",sum(p['category_name'] in('null','') for p in P))
print("top brands:",Counter(p['brand_name'] for p in P if p['brand_name']!='null').most_common(15))
print("brand values like متفرقه/no-brand:",[(b,c) for b,c in Counter(p['brand_name'] for p in P).items() if re.search('متفرقه|نامشخص|سایر|بدون|other',b,re.I)][:10])
print("model examples:",[p['model'] for p in P if p['model']!='null'][:8])
print("empty persian_title:",[p['product_id'] for p in P if not p['persian_title']])
