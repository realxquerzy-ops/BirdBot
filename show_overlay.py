import sys
import numpy as np
from PIL import Image
import ocr_mod

p = sys.argv[1]
x1 = int(sys.argv[2]) if len(sys.argv) > 2 else 340
frame = np.asarray(Image.open(p).convert("RGB"))
for scale in (2, 3):
    crop = Image.fromarray(frame).crop((0, 0, x1, 1080))
    crop = crop.resize((crop.width*scale, crop.height*scale), Image.LANCZOS)
    g = np.asarray(crop.convert("L"))
    inv = 255 - np.where(g > max(110, int(np.percentile(g, 70))), 255, 0).astype(np.uint8)
    print(f"===== scale {scale} =====")
    print(ocr_mod.ocr_img(Image.fromarray(inv)))
