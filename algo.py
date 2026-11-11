import time, re, random, sys
import ctypes
from ctypes import wintypes
import numpy as np
from PIL import Image
import gd_run as g, ocr_mod

H = None
random.seed(7)

u32 = g.u32

def mini_top(h):
    r = wintypes.RECT(); u32.GetWindowRect(h, ctypes.byref(r))
    if r.right - r.left < 400 or r.bottom - r.top < 400:
        g.top(h)
    else:
        fg = u32.GetForegroundWindow()
        u32.AttachThreadInput(g.k32.GetCurrentThreadId(), u32.GetWindowThreadProcessId(fg, None), True)
        u32.SetForegroundWindow(h); u32.BringWindowToTop(h)
        u32.AttachThreadInput(g.k32.GetCurrentThreadId(), u32.GetWindowThreadProcessId(fg, None), False)
        u32.SetWindowPos(h, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0040)

def read_frame():
    mini_top(H)
    img = Image.fromarray(g.grab()).crop((0, 0, 340, 300))
    img = img.resize((img.width*3, img.height*3), Image.LANCZOS)
    a = np.asarray(img.convert("L"))
    inv = 255 - np.where(a > max(110, int(np.percentile(a, 70))), 255, 0).astype(np.uint8)
    s = ocr_mod.ocr_img(Image.fromarray(inv))
    def gg1(p):
        m = re.search(p, s); return float(m.group(1)) if m else None
    return gg1(r"Time[:\s]*([0-9]+\.[0-9]+)"), gg1(r"[xX][:\s]*([0-9]+)"), gg1(r"Attempt[:\s]*([0-9]+)")

def new_att(targets):
    return {"fired": [False]*len(targets), "fire_t": [], "maxx": 0.0, "lastt": None}

def session(targets, seconds=10.0):
    windows = []
    cur = new_att(targets); wt = None
    t0 = time.time()
    while time.time() - t0 < seconds:
        t, x, att = read_frame()
        if t is not None and cur["lastt"] is not None and t < cur["lastt"] - 0.25:
            windows.append((cur["maxx"], list(cur["fire_t"]), cur["lastt"]))
            cur = new_att(targets); wt = att
            continue
        if att is not None and wt is not None and att > wt:
            windows.append((cur["maxx"], list(cur["fire_t"]), cur["lastt"]))
            cur = new_att(targets); wt = att
        if att is not None:
            wt = att
        if x is not None and x > cur["maxx"]:
            cur["maxx"] = x
        if t is not None:
            cur["lastt"] = t
        for i, tg in enumerate(targets):
            if not cur["fired"][i] and cur["lastt"] is not None and cur["lastt"] >= tg:
                g.tap(0x20); cur["fired"][i] = True; cur["fire_t"].append(round(cur["lastt"], 2))
        time.sleep(0.03)
    windows.append((cur["maxx"], list(cur["fire_t"]), cur["lastt"]))
    return windows

def clean(clicks):
    out = []
    for v in sorted(set(clicks)):
        if v is not None and 0.05 <= v <= 30:
            if not out or v - out[-1] >= 0.12:
                out.append(round(v, 2))
    return out

if __name__ == "__main__":
    H = g.find_gl()
    best_sched = [0.5]
    best_prog = 0.0
    best_dt = None
    g.top(H); time.sleep(0.2); g.tap(0x20); time.sleep(0.3)
    for it in range(int(sys.argv[1]) if len(sys.argv) > 1 else 20):
        wins = session(best_sched)
        for prog, clicks, dt in wins:
            if prog > best_prog:
                best_prog = prog
                best_sched = clean(clicks if clicks else best_sched)
                best_dt = dt
                print(f"it {it:2d}  NEW BEST x={prog:.0f}  clicks={best_sched}  death_t={dt}")
        if best_prog > 0:
            dt = best_dt if best_dt else best_prog / 311.0
            cand = clean(best_sched + [round(max(0.12, dt - 0.20), 2)])
            if cand == best_sched:
                cand = clean(best_sched + [round(max(0.12, dt - 0.10 - random.uniform(0, 0.15)), 2)])
        else:
            cand = [0.5]
        best_sched = cand
        if best_prog >= 3000:
            print("REACHED 3000+ ; stopping")
            break
    print("FINAL clicks:", best_sched, "best_x", best_prog)