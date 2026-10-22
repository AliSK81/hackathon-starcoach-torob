from load import *
from collections import Counter
O=read("offers")
x=[o for o in O if o['price_toman']=='1']
print("price==1 offers:",len(x),"shops:",len({o['shop_id'] for o in x}),"desc sample:",[o['description'][:50] for o in x if o['description']][:3])
