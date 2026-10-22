import os, sys, time, random, sqlite3
os.environ["HF_HUB_OFFLINE"] = "1"
import torch
torch.set_num_threads(int(sys.argv[1]) if len(sys.argv) > 1 else 4)
from sentence_transformers import SentenceTransformer
import numpy as np

OUT = os.path.dirname(os.path.abspath(__file__))
con = sqlite3.connect(os.path.join(OUT, "uni.db"))
rows = con.execute("SELECT raw, category FROM p").fetchall()
random.seed(0)
sample = random.sample(rows, 30000)
titles = [r[0] for r in sample]

t = time.perf_counter()
m = SentenceTransformer("intfloat/multilingual-e5-small", device="cpu")
print(f"threads={torch.get_num_threads()} load {time.perf_counter()-t:.1f}s")
t = time.perf_counter()
E = m.encode(["passage: " + x for x in titles], batch_size=64, normalize_embeddings=True, convert_to_numpy=True)
dt = time.perf_counter() - t
print(f"encoded {len(titles)} titles in {dt:.1f}s = {len(titles)/dt:.0f} titles/s; dim={E.shape[1]}; "
      f"extrapolated 225,903 titles: {225903/(len(titles)/dt)/60:.1f} min; matrix fp32 {225903*E.shape[1]*4/2**20:.0f} MiB")

for q in ["گوشی ارزون سامسونگ", "هندزفری بی سیم", "iphone 13", "شارژر فندکی ماشین", "لپ تاپ برای برنامه نویسی",
          "یخچال", "ساعت هوشمند"]:
    t = time.perf_counter()
    qv = m.encode(["query: " + q], normalize_embeddings=True)[0]
    s = E @ qv
    top = np.argsort(-s)[:3]
    print(f"\n{q}  ({(time.perf_counter()-t)*1000:.0f} ms incl. query encode, brute force over 30k)")
    for i in top:
        print(f"   {s[i]:.3f}  {titles[i]}  [{sample[i][1]}]")
