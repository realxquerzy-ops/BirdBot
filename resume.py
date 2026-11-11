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

H = g.find_gl()
g.focus(H); time.sleep(0.2)
g.tap(0x1B); time.sleep(0.5)
for i in range(10):
    s = read(g.grab())
    m = re.search(r"Time[:\s]*([0-9]+\.[0-9]+)", s)
    a = re.search(r"Attempt[:\s]*([0-9]+)", s)
    print(f"{i:2d} Time={m.group(1) if m else '-'} Att={a.group(1) if a else '-'}")
    time.sleep(0.5)
