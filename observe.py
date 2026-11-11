import time, re
import numpy as np
from PIL import Image
import gd_run as g, ocr_mod

def read(frame):
    img = Image.fromarray(frame).crop((0, 0, 340, 300))
    img = img.resize((img.width*3, img.height*3), Image.LANCZOS)
    a = np.asarray(img.convert("L"))
    inv = 255 - np.where(a > max(110, int(np.percentile(a, 70))), 255, 0).astype(np.uint8)
    return ocr_mod.ocr_img(Image.fromarray(inv))

for i in range(24):
    s = read(g.grab())
    def g1(p):
        m = re.search(p, s); return m.group(1) if m else "-"
    print(f"{i:2d} Time={g1(r'Time[:\s]*([0-9]+\.[0-9]+)')} Att={g1(r'Attempt[:\s]*([0-9]+)')} x={g1(r'[xX][:\s]*([0-9]+)')} y={g1(r'[Yy][:\s]*([0-9]+)')}")
    time.sleep(0.5)
