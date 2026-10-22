from load import *
from addr import norm
from collections import Counter
import re
S=read("shops"); A=[norm(s['address']) for s in S]
m=[re.search(r"علا\S{0,3}دین",a) for a in A]
print("addresses mentioning Alaeddin (regex علا\S{0,3}دین):",sum(1 for x in m if x),Counter(x.group(0) for x in m if x).most_common())
