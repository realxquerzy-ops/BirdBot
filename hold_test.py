import time, re, sys
import numpy as np
from PIL import Image
import gd_run as g, ocr_mod
from bg_cap import grab_print

H = None; RECT = None

def read(frm):
    img = Image.fromarray(frm).crop((0, 0, min(340, RECT[2]-RECT[0]), min(300, RECT[3]-RECT[1])))
    img = img.resize((img.width*3, img.height*3), Image.LANCZOS)
    a = np.asarray(img.convert("L"))
    p = np.percentile(a, 70)
    inv = 255 - np.where(a > max(110, int(p)), 255, 0).astype(np.uint8)
    s = ocr_mod.ocr_img(Image.fromarray(inv))
    def g1(pat):
        m = re.search(pat, s); return float(m.group(1)) if m else None
    return g1(r"Time[:\s]*([0-9]+\.[0-9]+)"), g1(r"[xX][:\s]*([0-9]+)"), g1(r"Attempt[:\s]*([0-9]+)")

def run_hold(D, natt=5, cap=7.0):
    prev_fg = g.u32.GetForegroundWindow()
    g.gentle_top(H); time.sleep(0.15); g.tap(0x20); time.sleep(0.4)
    t0 = time.time(); tlast = None; peak = 0.0; atts = 0; started = False; peaks = []
    while time.time() - t0 < natt*cap + 10 and atts < natt:
        frm, _ = grab_print(H)
        t, x, att = read(frm)
        if t is not None:
            if not started and t < 1.0:
                g.tap(0x20, hold=D); started = True; atts += 1
            elif started and tlast is not None and t < tlast - 0.3:
                g.tap(0x20, hold=D); atts += 1; peaks.append(round(peak)); print(f"  attempt#{atts} peak={peak:.0f}", flush=True)
            tlast = t
        if x is not None and x > peak: peak = x
        time.sleep(0.02)
    try: g.focus(prev_fg)
    except Exception: pass
    return peak, atts, peaks

if __name__ == "__main__":
    H = g.find_gl(); RECT = g.win_rect(H)
    print("hwnd", H, "rect", RECT, flush=True)
    for D in [float(x) for x in sys.argv[1].split(",")] if len(sys.argv) > 1 else [1.2]:
        p, na, ps = run_hold(D)
        print(f"hold={D}s atts={na} peak_x={p:.0f} peaks={ps}", "  << passed 800" if p > 800 else "", flush=True)