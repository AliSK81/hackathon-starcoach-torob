from load import *
from addr import *
from collections import Counter
import random, re
S=read("shops"); n=len(S)
A=[norm(s['address']) for s in S]
def rate(pat): 
    c=sum(1 for a in A if re.search(pat,a)); return f"{c} ({100*c/n:.1f}%)"
print("raw keyword presence (normalized address):")
for k in ["پاساژ","مجتمع","بازار","سرای|سرا ","تیمچه","ساختمان","برج","مرکز خرید",r"مال(?!\S)","طبقه","همکف","زیرهمکف|زیر همکف","زیرزمین","منفی","واحد","پلاک","مغازه","غرفه","بلوک","نبش","کوچه","خیابان"]:
    print(f"  {k}: {rate(k)}")
P=[parse(s['address']) for s in S]
for f in ["passage","floor_raw","floor","unit","plaque"]:
    c=sum(1 for p in P if p[f] is not None); print(f"parsed {f}: {c} ({100*c/n:.1f}%)")
print("unit or plaque:", sum(1 for p in P if p['unit'] or p['plaque']))
print("passage+floor+(unit|plaque):", sum(1 for p in P if p['passage'] and p['floor'] is not None and (p['unit'] or p['plaque'])))
print("floor_raw but floor value None:", Counter(p['floor_raw'] for p in P if p['floor_raw'] and p['floor'] is None).most_common(10))
print("floor values:", sorted(Counter(p['floor'] for p in P if p['floor'] is not None).items()))
print("passage kw:", Counter(p['passage_kw'] for p in P if p['passage_kw']).most_common())
# 'طبقه' present but not parsed
miss=[a for a,p in zip(A,P) if 'طبقه' in a and p['floor_raw'] is None]
print("طبقه present but floor unparsed:",len(miss)); [print("   ",m) for m in miss[:8]]
# passage name canonicalization
def canon(x):
    x=re.sub(r"علا[ءئ]?ا?لدین|علاالدین|علاءالدین|علائدین|علالدین","علاءالدین",x)
    x=re.sub(r"\s*(یک|1)$"," 1",x); x=re.sub(r"\s*(دو|2)$"," 2",x)
    return x.strip()
pc=Counter(canon(p['passage']) for p in P if p['passage'])
print("distinct passage names:",len(pc)); print("top 40 passages:"); [print(f"   {c} {k}") for k,c in pc.most_common(40)]
aladdin=[a for a in A if re.search(r"علا[ءئا]?[اء]?لدین|علالدین",a)]
print("addresses mentioning Alaeddin (any spelling):",len(aladdin))
print("spellings:",Counter(re.search(r"علا\S*دین",a).group(0) for a in aladdin if re.search(r"علا\S*دین",a)).most_common())
random.seed(7)
print("\n15 sample parses:")
idx=random.sample(range(n),11)+[i for i,(a,p) in enumerate(zip(A,P)) if 'طبقه' in a and p['floor'] is None][:2]+[i for i,p in enumerate(P) if 'سرا' in A[i]][:2]+[i for i,p in enumerate(P) if 'بعد از ساختمان' in A[i]][:1]
for i in idx: print(" ",S[i]['address'],"\n     ->",{k:v for k,v in P[i].items() if v is not None})
