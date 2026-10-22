from load import *
import math
S=read("shops")
pts=[(float(s['lat']),float(s['lon']),s['location_label']) for s in S]
# equirectangular metres
def d(a,b): 
    x=(a[1]-b[1])*math.cos(math.radians(35.7))*111320; y=(a[0]-b[0])*110540; return math.hypot(x,y)
agree=0; tot=0; nn=[]
import bisect
srt=sorted(range(len(pts)),key=lambda i:pts[i][0])
lats=[pts[i][0] for i in srt]
for i,p in enumerate(pts):
    lo=bisect.bisect_left(lats,p[0]-0.01); hi=bisect.bisect_right(lats,p[0]+0.01)
    best=None;bd=1e18
    for j in srt[lo:hi]:
        if j==i: continue
        dd=d(p,pts[j])
        if dd<bd: bd=dd;best=j
    if best is None: continue
    tot+=1; agree+= pts[best][2]==p[2]; nn.append(bd)
nn.sort()
print("1-NN label agreement",agree,"/",tot, f"{100*agree/tot:.1f}%")
print("nearest-neighbour distance m: p10 %.1f median %.1f p90 %.1f"%(nn[len(nn)//10],nn[len(nn)//2],nn[9*len(nn)//10]))
print("shops whose nearest other shop is <5m:",sum(x<5 for x in nn),"<1m:",sum(x<1 for x in nn))
