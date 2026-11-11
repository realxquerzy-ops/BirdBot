import time, re, sys
import numpy as np
from PIL import Image
import gd_run as g, ocr_mod

def read(frame):
    img = Image.fromarray(frame).crop((0, 0, 340, 300))
    img = img.resize((img.width*3, img.height*3), Image.LANCZOS)
    a = np.asarray(img.convert("L"))
    inv = 255 - np.where(a > max(110, int(np.percentile(a, 70))), 255, 0).astype(np.uint8)
    return ocr_mod.ocr_img(Image.fromarray(inv))

def run(tgt, cap=7.0):
    g.top(H); time.sleep(0.2)
    g.tap(0x20); time.sleep(0.4)
    t0 = time.time(); last = None; maxx = 0.0; maxt = 0.0
    jumped = False; windowatt = None; jumps_fired = 0
    while time.time() - t0 < cap:
        s = read(g.grab())
        def g1(p):
            m = re.search(p, s); return float(m.group(1)) if m else None
        t, x, att = g1(r"Time[:\s]*([0-9]+\.[0-9]+)"), g1(r"[xX][:\s]*([0-9]+)"), g1(r"Attempt[:\s]*([0-9]+)")
        if windowatt is None: windowatt = att
        if att is not None and windowatt is not None and att > windowatt:
            windowatt = att; jumped = False
        if t is not None and last is not None and t < last - 0.25:
            jumped = False
        if t is not None:
            if t > maxt: maxt = t
            last = t
            if x is not None and x > maxx: maxx = x
            if not jumped and t >= tgt and t < 0.62:
                g.tap(0x20); jumped = True; jumps_fired += 1
        time.sleep(0.03)
    return maxt, maxx, jumps_fired

if __name__ == "__main__":
    H = g.find_gl()
    tgts = [float(x) for x in sys.argv[1].split(",")] if len(sys.argv) > 1 else [0.3, 0.4, 0.5]
    for T in tgts:
        mt, mx, jf = run(T)
        print(f"tgt={T}  maxTime={mt:.2f}  maxX={mx:.0f}  jumps={jf}  {'<< PASSED x208' if mx > 250 else ''}")