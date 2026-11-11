import sys
import numpy as np
from PIL import Image

path = sys.argv[1] if len(sys.argv) > 1 else "frame.png"
img = Image.open(path).convert("RGB")
a = np.asarray(img)
H, W, _ = a.shape
print(f"image {W}x{H}")

# quantize to reduce color count
q = (a // 16).astype(np.uint8)
flat = q.reshape(-1, 3)
uniq, inv, counts = np.unique(flat, axis=0, return_inverse=True, return_counts=True)
order = np.argsort(counts)[::-1]

print(f"distinct quantized colors: {len(uniq)}")
print("top colors (r,g,b approx = q*16+8)  pct  centroid(x,y)  bbox(x0,y0,x1,y1)")
total = H * W
inv = inv.reshape(H, W)
for idx in order[:25]:
    c = uniq[idx]
    cnt = counts[idx]
    ys, xs = np.where(inv == idx)
    cx, cy = int(xs.mean()), int(ys.mean())
    print(f"  ({c[0]*16+8:3d},{c[1]*16+8:3d},{c[2]*16+8:3d})  {100*cnt/total:5.2f}%  "
          f"({cx:4d},{cy:4d})  bbox=({xs.min()},{ys.min()},{xs.max()},{ys.max()})")
