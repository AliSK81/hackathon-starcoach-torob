from load import *
from collections import Counter
from urllib.parse import urlparse
import urllib.request, random
P=read("products")
n=Counter(); dom=Counter(); ext=Counter(); urls=[]
for p in P:
    u=J(p['image_urls']) or []
    n[len(u)]+=1
    for x in u: dom[urlparse(x).netloc]+=1; ext[x.rsplit('.',1)[-1].lower()[:5]]+=1; urls.append(x)
print("images per product:",sorted(n.items())[:15],"... max",max(n)); print("domains:",dom); print("extensions:",ext.most_common(6))
print("path prefixes:",Counter('/'.join(urlparse(x).path.split('/')[:3]) for x in urls).most_common(4))
random.seed(11)
for u in random.sample(urls,3):
    try:
        r=urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0"}),timeout=20)
        b=r.read(); print("GET",u,"->",r.status,r.headers.get('Content-Type'),len(b),"bytes", "cache:",r.headers.get('Cache-Control'), "CORS:",r.headers.get('Access-Control-Allow-Origin'))
    except Exception as e: print("GET",u,"->",repr(e)[:200])
