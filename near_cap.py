import time, re
import numpy as np
from PIL import Image
import gd_run as g, ocr_mod
from bg_cap import grab_print

H = None; RECT = None

def read(frm):
    img = Image.fromarray(frm).crop((0, 0, min(340, RECT[2]-RECT[0]), min(300, RECT[3]-RECT[1])))
    img = img.resize((img.width*3, img.height*3), Image.LANCZOS)
    a = np.asarray(img.convert("L"))
    inv = 255 - np.where(a > max(110, int(np.percentile(a, 70))), 255, 0).astype(np.uint8)
    s = ocr_mod.ocr_img(Image.fromarray(inv))
    def g1(pat):
        m = re.search(pat, s); return float(m.group(1)) if m else None
    return g1(r"Time[:\s]*([0-9]+\.[0-9]+)"), g1(r"[xX][:\s]*([0-9]+)")

def run(D=1.4):
    g.gentle_top(H); time.sleep(0.15); g.tap(0x20); time.sleep(0.4)
    t0 = time.time(); tlast = None; started = False; savedx = {}
    while time.time() - t0 < 45:
        frm, _ = grab_print(H)
        t, x = read(frm)
        if t is not None:
            if not started and t < 1.0:
                g.tap(0x20, hold=D); started = True
            elif started and tlast is not None and t < tlast - 0.3:
                g.tap(0x20, hold=D)
            if started and x is not None and x >= 820:
                k = int(x)
                if k not in savedx:
                    savedx[k] = frm.copy()
                    Image.fromarray(frm).save(f"near_{k}.png")
                    if len(savedx) >= 14: break
            tlast = t
        time.sleep(0.015)

if __name__ == "__main__":
    H = g.find_gl(); RECT = g.win_rect(H)
    run(1.4)
    import glob; print("saved:", sorted(int(f.split("_")[1][:-4]) for f in glob.glob("near_*.png")), flush=True)