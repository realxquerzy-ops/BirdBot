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
    return g1(r"Time[:\s]*([0-9]+\.[0-9]+)"), g1(r"[xX][:\s]*([0-9]+)"), g1(r"Attempt[:\s]*([0-9]+)")

ASC = " .:-=+*#%@"

def ascii_blob(a, x0, y0, x1, y1, w=130):
    sub = a[y0:y1, x0:x1]
    h, W = sub.shape[:2]
    r = sub[..., 0].astype(float); gg = sub[..., 1].astype(float); b = sub[..., 2].astype(float)
    bri = (r + gg + b) / 3.0
    red = r - (gg + b) / 2.0; grn = gg - (r + b) / 2.0
    img = Image.fromarray(sub).resize((w, max(3, int(h / W * w * 0.55))), Image.LANCZOS)
    small = np.asarray(img).astype(float)
    rr, ggg, bb = small[..., 0], small[..., 1], small[..., 2]
    b2 = (rr + ggg + bb) / 3.0
    redd = rr - (ggg + bb) / 2.0; grnn = ggg - (rr + bb) / 2.0
    ch = np.full(small.shape[:2], ' ')
    ch[b2 > 40] = '.'
    ch[(redd > 25) & (redd > grnn)] = 'R'
    ch[(grnn > 20) & (grnn >= redd)] = 'G'
    ch[(b2 > 40) & (redd < 25) & (grnn < 20)] = '#'
    ch[(b2 > 220) & (redd < 25) & (grnn < 20)] = 'W'
    for i in range(len(ch)):
        print("".join(ch[i]).rstrip())

def run_view(D=1.4):
    g.gentle_top(H); time.sleep(0.15); g.tap(0x20); time.sleep(0.4)
    t0 = time.time(); tlast = None; atts = 0; started = False; saved = 0
    while time.time() - t0 < 40 and saved < 12:
        frm, _ = grab_print(H)
        t, x, att = read(frm)
        if t is not None:
            if not started and t < 1.0:
                g.tap(0x20, hold=D); started = True; atts += 1
            elif started and tlast is not None and t < tlast - 0.3:
                g.tap(0x20, hold=D); atts += 1
            if started and x is not None and 640 <= x <= 897:
                Image.fromarray(frm).save(f"traj_{saved}_{int(x)}.png")
                saved += 1
            tlast = t
        time.sleep(0.02)

if __name__ == "__main__":
    H = g.find_gl(); RECT = g.win_rect(H)
    print("hwnd", H, "rect", RECT, flush=True)
    run_view(1.4)
    print("saved", sorted([f for f in __import__("glob").glob("traj_*.png")]), flush=True)