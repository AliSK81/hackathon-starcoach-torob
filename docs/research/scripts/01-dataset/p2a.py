from load import *
import random
S=read("shops"); random.seed(1)
for s in random.sample(S,40): print(s['location_label'],'|',s['address'])
