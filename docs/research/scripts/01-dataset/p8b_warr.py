from load import *
from collections import Counter
import re, random
O=read("offers"); S=read("shops")
W=[J(o['warranty']) for o in O]; W=[w for w in W if w]
print("offers with warranty:",len(W))
print("key sets:",Counter(tuple(sorted(w.keys())) for w in W))
print("period_months:",Counter(w.get('period_months') for w in W).most_common(12))
print("provider null:",sum(1 for w in W if not w.get('provider')),"top providers:",Counter(w.get('provider') for w in W).most_common(10))
print("description examples:",Counter(w.get('description') for w in W).most_common(6))
random.seed(2)
d=[o['description'] for o in O if re.search('ترب ?‌?پی|اقساط|قسطی',o['description'])]
print("desc mentioning installments sample:",[x[:90] for x in random.sample(d,4)])
d=[o['description'] for o in O if o['description']]
print("random descriptions:",[x[:90] for x in random.sample(d,6)])
print("desc mentions موجود/ناموجود/تماس:",{k:sum(1 for x in d if k in x) for k in ['موجود','ناموجود','تماس','استعلام','عمده','حداقل سفارش']})
