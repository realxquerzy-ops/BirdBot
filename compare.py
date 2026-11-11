import numpy as np
from PIL import Image
import os

files = ["frame.png", "state_a.png", "game_a.png", "game_live.png", "pw.png"]
imgs = {}
for f in files:
    if os.path.exists(f):
        imgs[f] = np.asarray(Image.open(f).convert("RGB")).astype(np.int16)
names = list(imgs)
print("shapes:", {f: imgs[f].shape for f in names})
for i in range(len(names)):
    for j in range(i + 1, len(names)):
        a, b = imgs[names[i]], imgs[names[j]]
        if a.shape == b.shape:
            d = np.abs(a - b).sum(2)
            print(f"{names[i]:16s} vs {names[j]:16s} diff={100*(d>30).mean():6.2f}%  meanabs={d.mean():.1f}")
