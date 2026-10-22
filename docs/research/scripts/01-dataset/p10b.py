from load import *
import urllib.request
P=read("products")
odd=[x for p in P for x in (J(p['image_urls']) or []) if '.' not in x.rsplit('/',1)[-1]][:2]
web=[x for p in P for x in (J(p['image_urls']) or []) if x.endswith('.webp')][:1]
for u in odd+web:
    try:
        r=urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0"}),timeout=20); b=r.read()
        print(u,"->",r.status,r.headers.get('Content-Type'),len(b))
    except Exception as e: print(u,"->",repr(e)[:150])
