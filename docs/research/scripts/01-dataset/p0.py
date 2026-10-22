from load import *
for n in ["shops","products","offers"]:
    r = read(n); print(n, len(r), list(r[0].keys()))
    print(r[0])
