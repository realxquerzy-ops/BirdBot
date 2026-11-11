import time, re
import numpy as np
from PIL import Image
import gd_run as g, ocr_mod

H = None
DS = 8

def comps(mask):
    Hh, W = mask.shape
    seen = np.zeros_like(mask, bool); out = []
    for y in range(Hh):
        for x in range(W):
            if mask[y, x] and not seen[y, x]:
                stack = [(x, y)]; seen[y, x] = True; pts = []
                while stack:
                    cx, cy = stack.pop(); pts.append((cx, cy))
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nx, ny = cx + dx, cy + dy
                        if 0 <= nx < W and 0 <= ny < Hh and mask[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = True; stack.append((nx, ny))
                if len(pts) >= 2:
                    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
                    out.append((min(xs)*DS, min(ys)*DS, (max(xs)+1)*DS, (max(ys)+1)*DS, len(pts)))
    return out

def analyze(arr):
    small = np.asarray(Image.fromarray(arr).resize((240, 135), Image.BILINEAR)).astype(float)
    r, gg, b = small[..., 0], small[..., 1], small[..., 2]
    mx = small.max(2); mn = small.min(2); val = mx
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0)
    hue = np.zeros_like(mx); d = np.maximum(mx - mn, 1e-6)
    m = (mx == r); hue[m] = (60 * ((gg - b) / d) % 360)[m]
    m = (mx == gg); hue[m] = (60 * ((b - r) / d) + 120)[m]
    m = (mx == b); hue[m] = (60 * ((r - gg) / d) + 240)[m]
    red = (val > 70) & (sat > 0.3) & ((hue < 25) | (hue > 335))
    haz = (val > 60) & (sat > 0.35) & (hue >= 45) & (hue <= 170)
    rl = sorted(comps(red), key=lambda c: c[4], reverse=True)
    hl = sorted(comps(haz), key=lambda c: c[4], reverse=True)
    return rl, hl

def read_x():
    g.top(H)
    img = Image.fromarray(g.grab()).crop((0, 0, 340, 300))
    img = img.resize((img.width*3, img.height*3), Image.LANCZOS)
    a = np.asarray(img.convert("L"))
    inv = 255 - np.where(a > max(110, int(np.percentile(a, 70))), 255, 0).astype(np.uint8)
    s = ocr_mod.ocr_img(Image.fromarray(inv))
    m = re.search(r"[xX][:\s]*([0-9]+)", s)
    return int(m.group(1)) if m else None

if __name__ == "__main__":
    H = g.find_gl()
    g.top(H); time.sleep(0.2); g.tap(0x20); time.sleep(0.3)
    px = 704.0
    prev = None; prev_t = None; v = 95.0; last_jump = 0.0; peak_x = 0
    tstart = time.time()
    while time.time() - tstart < 35.0:
        arr = np.asarray(Image.fromarray(g.grab()).convert("RGB"))
        rs, hs = analyze(arr)
        if rs:
            cx = (rs[0][0] + rs[0][2]) / 2.0
            px = 0.6*px + 0.4*cx
        ahead = sorted([(h[0] + h[2]) / 2.0 for h in hs if (h[0] + h[2]) / 2.0 > px])
        now = time.time()
        if prev is not None and prev_t and now - prev_t > 0.05:
            d = prev - px
            if d != 0 and now - prev_t > 0.03:
                inst = d / (now - prev_t)
                if 0 < inst < 500: v = 0.5*v + 0.5*inst
        prev = px; prev_t = now
        if ahead and now - last_jump > 0.45:
            hx = ahead[0]
            eta = (hx - px) / max(v, 1.0)
            if eta <= 0.34:
                g.tap(0x20); last_jump = time.time()
        if now - tstart > 1.0:
            tstart = time.time()
            x = read_x()
            if x and x > peak_x: peak_x = x
            print(f"px={px:.0f} v={v:.0f} ahead={[round(h-px) for h in ahead[:3]]} peak_x={peak_x}")
        time.sleep(0.02)
    print("DONE peak_x", peak_x)