import time, re
import numpy as np
from PIL import Image
import gd_run as g, ocr_mod

H = None

def read(tl, tt, tr, tb):
    g.top(H)
    im = Image.fromarray(g.grab()).crop((tl, tt, tr, tb))
    im = im.resize((im.width*3, im.height*3), Image.LANCZOS)
    a = np.asarray(im.convert("L"))
    inv = 255 - np.where(a > max(110, int(np.percentile(a, 70))), 255, 0).astype(np.uint8)
    return ocr_mod.ocr_img(Image.fromarray(inv))

def read_t_a():
    s = read(10, 55, 130, 160)
    mt = re.search(r"Time[:\s]*([0-9]+\.[0-9]+)", s)
    ma = re.search(r"Attempt[:\s]*([0-9]+)", s)
    return (float(mt.group(1)) if mt else None, int(ma.group(1)) if ma else None)

def one_run(targets, gamemaxt=1.6):
    g.top(H)
    whole = read(0, 0, 340, 1080)
    if "Global" in whole or "Bypass" in whole:
        g.tap(0x09); time.sleep(0.5)
    g.top(H); g.tap(g.VK_R); time.sleep(0.4)
    tstart = time.time(); last = None; maxT = 0.0; death = None
    fired = [False]*len(targets); started = False
    realcap = gamemaxt*12 + 12
    while time.time() - tstart < realcap:
        tv, av = read_t_a()
        if tv is not None:
            if not started:
                g.tap(0x20); started = True
            if last is not None and tv < last - 0.2:
                death = last; break
            if tv > maxT: maxT = tv
            last = tv
        for i, tg in enumerate(targets):
            if not fired[i] and last is not None and last >= tg:
                g.tap(0x20); fired[i] = True
        time.sleep(0.04)
    return maxT, death, started

if __name__ == "__main__":
    H = g.find_gl()
    for k in range(3):
        mt, dt, st = one_run([0.7, 1.4])
        print(f"run {k}: started={st} maxTime={mt:.2f} death={dt}")
