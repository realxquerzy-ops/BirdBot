import time, re, sys
import numpy as np
from PIL import Image
import gd_run as g, ocr_mod

VK_SPACE = 0x20
H = None

def read_t_a():
    g.top(H)
    im = Image.fromarray(g.grab()).crop((10, 55, 130, 160)).resize((360, 315), Image.LANCZOS)
    a = np.asarray(im.convert("L"))
    inv = 255 - np.where(a > max(110, int(np.percentile(a, 70))), 255, 0).astype(np.uint8)
    s = ocr_mod.ocr_img(Image.fromarray(inv))
    mt = re.search(r"Time[:\s]*([0-9]+\.[0-9]+)", s)
    ma = re.search(r"Attempt[:\s]*([0-9]+)", s)
    return (float(mt.group(1)) if mt else None,
            int(ma.group(1)) if ma else None, s)

def attempt(targets, gamemaxt=40.0):
    g.top(H); g.tap(g.VK_R); time.sleep(0.25)
    targets = sorted(targets)
    fired = [False]*len(targets)
    last = None; startA = None; maxT = 0.0; death = None
    tstart = time.time()
    realcap = gamemaxt*4.0 + 15.0
    while time.time() - tstart < realcap:
        tv, av, s = read_t_a()
        if av is not None and startA is None:
            startA = av
        if tv is not None:
            if last is not None and (tv < last - 0.2 or
                    (av is not None and startA is not None and av > startA)):
                death = last; break
            if tv > maxT: maxT = tv
            last = tv
        for i, tg in enumerate(targets):
            if not fired[i] and last is not None and last >= tg:
                g.tap(VK_SPACE); fired[i] = True
        time.sleep(0.008)
    return maxT, death

if __name__ == "__main__":
    H = g.find_gl()
    targets = [0.0]
    for it in range(int(sys.argv[1]) if len(sys.argv) > 1 else 8):
        mt, dt = attempt(targets)
        print(f"iter {it:2d}  targets={[round(t,2) for t in targets]}  maxTime={mt:.2f}  death={dt}")
        if dt is None:
            print("  -> no death detected (survived window)")
            break
        nt = max(0.02, dt - 0.10)
        if any(abs(nt - t) < 0.10 for t in targets):
            nt = max(0.02, dt - 0.20)
        if any(abs(nt - t) < 0.08 for t in targets):
            print("  -> cannot place, stopping")
            break
        targets.append(round(nt, 2))
