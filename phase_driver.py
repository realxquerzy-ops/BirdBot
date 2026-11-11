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
    inv = 255 - np.where(a > max(110, int(np.percentile(a, 70))), 255, 0).astype(np.uint8)
    s = ocr_mod.ocr_img(Image.fromarray(inv))
    def g1(pat):
        m = re.search(pat, s); return float(m.group(1)) if m else None
    return g1(r"Time[:\s]*([0-9]+\.[0-9]+)"), g1(r"[xX][:\s]*([0-9]+)")

def run(D_total=8.0, T_tap=None, natt=6, timeout=90):
    prev_fg = g.u32.GetForegroundWindow()
    g.gentle_top(H); time.sleep(0.15); g.tap(0x20); time.sleep(0.4)
    t0 = time.time(); last_t = None; peak = 0.0; frozen = False; press_on = None; taps = []; durs = []
    atts = 0; spawn_t = None; tap_at = None
    while time.time() - t0 < timeout and atts < natt:
        frm, _ = grab_print(H)
        t, x = read(frm)
        now = time.time()
        if t is not None:
            if last_t is not None and t == last_t and not frozen:
                frozen = True; press_on = now
                g.u32.keybd_event(0x20, 0, 0, 0)
            if last_t is not None and t < last_t - 0.3:
                if frozen:
                    durs.append(now - press_on)
                    atts += 1
                    print(f"  attempt#{atts} freeze={now-press_on:.2f}s peak={peak:.0f}", flush=True)
                frozen = False; spawn_t = now
                if T_tap is not None: tap_at = now + T_tap
            last_t = t
        if press_on is not None and now - press_on >= D_total:
            g.u32.keybd_event(0x20, 0, 2, 0); press_on = None
        if tap_at is not None and now >= tap_at:
            g.tap(0x20, hold=0.18); tap_at = None; taps.append(round(now - spawn_t, 2))
        if x is not None and x > peak: peak = x
        time.sleep(0.015)
    g.u32.keybd_event(0x20, 0, 2, 0)
    try: g.focus(prev_fg)
    except Exception: pass
    return peak, atts, durs, taps

if __name__ == "__main__":
    H = g.find_gl(); RECT = g.win_rect(H)
    print("hwnd", H, "rect", RECT, flush=True)
    D_tot = float(sys.argv[1]) if len(sys.argv) > 1 else 8.0
    t_tap = float(sys.argv[2]) if len(sys.argv) > 2 else None
    p, na, durs, taps = run(D_total=D_tot, T_tap=t_tap)
    print(f"D_total={D_tot} taps={t_tap} atts={na} peak_x={p:.0f} FreezeDurs={[round(d,2) for d in durs]}", flush=True)