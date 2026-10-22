import re
FA2EN=str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩","01234567890123456789")
def norm(s):
    s=s.replace("ي","ی").replace("ك","ک").replace("‌"," ").translate(FA2EN)
    s=s.replace("پاساز","پاساژ").replace("هم کف","همکف").replace("زیر زمین","زیرزمین").replace("طبقه ی ","طبقه ").replace("طبقه‌ی","طبقه")
    return re.sub(r"\s+"," ",s).strip()
SEP=r"[،,\-\(\)]"
# passage / building: keyword + name up to next separator or floor/unit keyword
KW_P=r"(?:پاساژ|مجتمع(?:\s+تجاری)?|بازار(?:چه)?|سرای|سرا|تیمچه|مرکز\s+خرید|ساختمان|برج|مال)"
RE_PASSAGE=re.compile(r"(?P<kw>"+KW_P+r")\s+(?P<name>[^،,\-\(\)]+?)(?=\s*(?:"+SEP+r"|طبقه|واحد|پلاک|مغازه|بلوک|$))")
ORD={"همکف":0,"زیرین":-1,"زیرهمکف":-1,"زیر همکف":-1,"زیرزمین":-1,"منفی یک":-1,"منفی دو":-2,"منفی سه":-3,"اول":1,"یکم":1,"دوم":2,"سوم":3,"چهارم":4,"پنجم":5,"ششم":6,"هفتم":7,"هشتم":8,"نهم":9,"دهم":10,"یک":1,"دو":2,"سه":3,"چهار":4,"پنج":5,"شش":6,"هفت":7,"هشت":8,"نه":9,"ده":10,"اداری":None,"بالا":None,"همکف تجاری":0,"لابی":0,"مثبت یک":1}
FLOOR_WORDS="|".join(sorted(map(re.escape,ORD),key=len,reverse=True))
RE_FLOOR=re.compile(r"(?:طبقه|طبقات)\s*:?\s*(?P<val>(?:منفی|-|مثبت|\+)?\s*\d+|"+FLOOR_WORDS+r")")
RE_FLOOR_ALT=re.compile(r"(?<!\S)(?P<val>همکف|زیرهمکف|زیر همکف|زیرزمین)(?!\S)")
RE_UNIT=re.compile(r"(?P<kw>واحد|پلاک|مغازه|غرفه)\s*:?\s*(?:شماره\s*)?(?P<val>[0-9]+(?:[./][0-9]+)?\s*[A-Za-zآ-ی]?(?:\s*و\s*[0-9]+)?)")
def floor_val(v):
    v=v.strip().replace(" ","")
    m=re.match(r"(منفی|-)?(مثبت|\+)?(\d+)$",v)
    if m: return -int(m.group(3)) if m.group(1) else int(m.group(3))
    for k,x in ORD.items():
        if k.replace(" ","")==v: return x
    return None
def parse(addr):
    a=norm(addr); out={"passage":None,"passage_kw":None,"floor":None,"floor_raw":None,"unit":None,"plaque":None}
    cands=[m for m in RE_PASSAGE.finditer(a) if not re.search(r"(بعد از|قبل از|روبروی|روبه رو|جنب|نرسیده به|بالاتر از|پایین تر از|کنار|پشت)\s*$",a[:m.start()])]
    PRI={"پاساژ":0,"مجتمع تجاری":0,"مجتمع":0,"سرای":0,"سرا":0,"بازارچه":0,"بازار":1,"مرکز خرید":0,"مال":1,"برج":2,"ساختمان":2}
    if cands:
        m=min(cands,key=lambda m:PRI.get(re.sub(r"\s+"," ",m.group("kw")),3))
        out["passage"]=m.group("name").strip(); out["passage_kw"]=m.group("kw")
    m=RE_FLOOR.search(a) or RE_FLOOR_ALT.search(a)
    if m: out["floor_raw"]=m.group(0); out["floor"]=floor_val(m.group("val"))
    for m in RE_UNIT.finditer(a):
        k=m.group("kw"); v=m.group("val").strip()
        if k=="پلاک": out["plaque"]=out["plaque"] or v
        else: out["unit"]=out["unit"] or v
    return out
