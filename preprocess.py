import sys
import numpy as np
from PIL import Image

src, out = sys.argv[1], sys.argv[2]
crop = [int(x) for x in sys.argv[3:7]] if len(sys.argv) >= 7 else None
thr = int(sys.argv[7]) if len(sys.argv) > 7 else None
img = Image.open(src).convert("RGB")
if crop:
    img = img.crop(tuple(crop))
scale = 2
img = img.resize((img.width * scale, img.height * scale), Image.LANCZOS)
g = np.asarray(img.convert("L"))
t = thr if thr is not None else max(130, int(np.percentile(g, 80)))
inv = 255 - np.where(g > t, 255, 0).astype(np.uint8)
Image.fromarray(inv).save(out)
print(f"{src} crop={crop} thr={t} -> {out} {inv.shape[::-1]}")
