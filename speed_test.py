import time, re
import numpy as np
from PIL import Image
import gd_run as g, ocr_mod

H = g.find_gl()

def readtime():
    g.top(H)
    im = Image.fromarray(g.grab()).crop((10, 55, 120, 95)).resize((440, 160), Image.LANCZOS)
    a = np.asarray(im.convert("L"))
    inv = 255 - np.where(a > max(110, int(np.percentile(a, 70))), 255, 0).astype(np.uint8)
    t0 = time.time()
    s = ocr_mod.ocr_img(Image.fromarray(inv))
    dt = time.time() - t0
    m = re.search(r"([0-9]+\.[0-9]+)", s)
    return (m.group(1) if m else s), dt

g.top(H); time.sleep(0.2)
g.tap(g.VK_R); time.sleep(0.3); g.tap(g.VK_SPACE); time.sleep(0.05)
t0 = time.time(); time.sleep(2.0)
wall = time.time() - t0
val, dt = readtime()
print(f"wall={wall:.2f}s  Time={val}  ocr={dt*1000:.0f}ms")
