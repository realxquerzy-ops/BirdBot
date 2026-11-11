import sys
import numpy as np
from PIL import Image

src = sys.argv[1] if len(sys.argv) > 1 else "interact_last.png"
img = Image.open(src).convert("RGB")
x0, y0, x1, y1 = 0, 0, 230, 1080
crop = img.crop((x0, y0, x1, y1))
scale = 3
crop = crop.resize((crop.width * scale, crop.height * scale), Image.LANCZOS)
gray = np.asarray(crop.convert("L")).astype(np.uint8)

# text is bright on dark bg -> make black text on white for OCR
thr = np.percentile(gray, 70)
bw = np.where(gray > max(110, thr), 255, 0).astype(np.uint8)
out = 255 - bw  # invert: black text, white bg
Image.fromarray(out).save("labels_bw.png")
Image.fromarray(gray).save("labels_gray.png")
print(f"crop=({x0},{y0},{x1},{y1}) scale={scale} thr={max(110,int(thr))} -> labels_bw.png {out.shape[::-1]}")
