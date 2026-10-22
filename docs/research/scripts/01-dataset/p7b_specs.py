from load import *
from collections import Counter, defaultdict
import re, unicodedata
P=read("products"); O=read("offers")
print("titles w/ Arabic presentation forms (U+FB50-FEFF):",sum(1 for p in P if re.search('[ﭐ-﷿ﹰ-﻾]',p['persian_title'])))
print("seller_title with leading/trailing whitespace:",sum(1 for o in O if o['seller_title']!=o['seller_title'].strip()))
cat=defaultdict(lambda:[0,0,0]); keys=Counter(); secs=Counter(); nspec=[]
eng_name=0
for p in P:
    sp=J(p['specs']) or []
    c=cat[p['category_name']]; c[0]+=1; c[1]+= bool(sp); c[2]+=len(sp)
    if sp: nspec.append(len(sp))
    for d in sp: keys[d['key']]+=1; secs[d['section']]+=1
    if any(d['key']=='نام محصول' and re.search('[A-Za-z]',d['value']) for d in sp): eng_name+=1
nspec.sort()
print("products with specs:",len(nspec),"median #specs",nspec[len(nspec)//2],"max",nspec[-1])
print("products with Latin 'نام محصول' spec (proxy English title):",eng_name)
print("top spec keys:",keys.most_common(20)); print("top sections:",secs.most_common(8))
oc=Counter(); pcat={p['product_id']:p['category_name'] for p in P}
for o in O: oc[pcat[o['product_id']]]+=1
print("\nspec coverage for top-25 categories by offers: category | offers | products | % with specs | avg specs")
for k,v in oc.most_common(25):
    c=cat[k]; print(f"{k} | {v} | {c[0]} | {100*c[1]/c[0]:.0f}% | {c[2]/c[0]:.1f}")
print("\nimage_urls: products with 0 images", sum(1 for p in P if (J(p['image_urls']) or [])==[]))
