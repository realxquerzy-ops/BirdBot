import time, re, sys
import numpy as np
from PIL import Image
import gd_run as g, ocr_mod
from bg_cap import grab_print

H = None; RECT = None; TAPLEN = 0.18

def read(frm):
    img = Image.fromarray(frm).crop((0, 0, min(340, RECT[2]-RECT[0]), min(300, RECT[3]-RECT[1])))
    img = img.resize((img.width*3, img.height*3), Image.LANCZOS)
    a = np.asarray(img.convert("L"))
    inv = 255 - np.where(a > max(110, int(np.percentile(a, 70))), 255, 0).astype(np.uint8)
    s = ocr_mod.ocr_img(Image.fromarray(inv))
    def g1(pat):
        m = re.search(pat, s); return float(m.group(1)) if m else None
    return g1(r"Time[:\s]*([0-9]+\.[0-9]+)"), g1(r"[xX][:\s]*([0-9]+)"), g1(r"Attempt[:\s]*([0-9]+)")

def run_sched(holdD, taps, natt=4, cap=9.0):
    prev_fg = g.u32.GetForegroundWindow()
    g.gentle_top(H); time.sleep(0.15); g.tap(0x20); time.sleep(0.4)
    t0 = time.time(); tlast = None; peak = 0.0; atts = 0; started = False; peaks = []
    while time.time() - t0 < natt*cap + 10 and atts < natt:
        frm, _ = grab_print(H)
        t, x, att = read(frm)
        if t is not None:
            if not started and t < 1.0:
                g.tap(0x20, hold=holdD); started = True; atts += 1; fired = [False]*len(taps)
            elif started and tlast is not None and t < tlast - 0.3:
                g.tap(0x20, hold=holdD); atts += 1; fired = [False]*len(taps)
                peaks.append(round(peak)); print(f"  attempt#{atts} peak={peak:.0f}", flush=True)
            if started:
                for i, T in enumerate(taps):
                    if not fired[i] and t >= T:
                        g.tap(0x20, hold=TAPLEN); fired[i] = True
            tlast = t
        if x is not None and x > peak: peak = x
        time.sleep(0.02)
    try: g.focus(prev_fg)
    except Exception: pass
    return peak, atts, peaks

if __name__ == "__main__":
    H = g.find_gl(); RECT = g.win_rect(H)
    print("hwnd", H, "rect", RECT, flush=True)
    for T in [float(x) for x in sys.argv[1].split(",")] if len(sys.argv) > 1 else [1.7, 1.9]:
        p, na, ps = run_sched(1.4, [T])
        print(f"hold1.4+tap@{T}s atts={na} peak_x={p:.0f} peaks={ps}", "  << past 897!" if p > 897 else "", flush=True)