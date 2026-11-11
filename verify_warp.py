import time
import numpy as np
from PIL import Image
import gd_run as g, ocr_mod

def ocr_left():
    g.top(H)
    img = Image.fromarray(g.grab()).crop((0, 0, 340, 1080)).resize((680, 2160), Image.LANCZOS)
    a = np.asarray(img.convert("L"))
    inv = 255 - np.where(a > max(110, int(np.percentile(a, 70))), 255, 0).astype(np.uint8)
    return ocr_mod.ocr_img(Image.fromarray(inv))

H = g.find_gl()
txt = ocr_left()
print("menu?", ("Global" in txt or "Bypass" in txt))
if "Global" in txt or "Bypass" in txt:
    g.tap(0x09); time.sleep(0.5)
g.top(H); time.sleep(0.2)
g.tap(g.VK_R); time.sleep(0.25); g.tap(g.VK_SPACE); time.sleep(0.45)
print("----")
print(ocr_left())
