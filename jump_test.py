import time, re, sys
import numpy as np
from PIL import Image
import gd_run as g, ocr_mod

H = None

def read():
    g.top(H)
    img = Image.fromarray(g.grab()).crop((0, 0, 340, 300))
    img = img.resize((img.width*3, img.height*3), Image.LANCZOS)
    a = np.asarray(img.convert("L"))
    inv = 255 - np.where(a > max(110, int(np.percentile(a, 70))), 255, 0).astype(np.uint8)
    s = ocr_mod.ocr_img(Image.fromarray(inv))
    def g1(p):
        m = re.search(p, s); return float(m.group(1)) if m else None
    return g1(r"Time[:\s]*([0-9]+\.[0-9]+)"), g1(r"[xX][:\s]*([0-9]+)"), g1(r"Attempt[:\s]*([0-9]+)")

def run(target, cap=3.0):
    g.top(H); g.tap(g.VK_R); time.sleep(0.35)
    t0 = time.time(); last = None; maxt = 0.0; maxx = 0.0
    startatt = None; fired = False
    while time.time() - t0 < cap + 6:
        t, x, att = read()
        if startatt is None and att is not None:
            startatt = att
        if att is not None and startatt is not None and att > startatt:
            break
        if t is not None:
            if last is not None and t < last - 0.2:
                break
            if t > maxt: maxt = t
            if x is not None and x > maxx: maxx = x
            last = t
            if not fired and t >= target:
                g.tap(0x20); fired = True
        time.sleep(0.05)
    return maxt, maxx

if __name__ == "__main__":
    H = g.find_gl()
    for T in [0.25, 0.4, 0.55]:
        mt, mx = run(T)
        print(f"target={T}  maxTime={mt:.2f}  maxX={mx:.0f}  {'PASSED' if mx > 250 else ''}")
