import time
import numpy as np
from PIL import Image
import gd_run as g

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
    return sorted(comps(red), key=lambda c: c[4], reverse=True)[:4], sorted(comps(haz), key=lambda c: c[4], reverse=True)[:14]

if __name__ == "__main__":
    H = g.find_gl()
    g.top(H); time.sleep(0.2); g.tap(0x20); time.sleep(0.3)
    arr = np.asarray(Image.fromarray(g.grab()).convert("RGB"))
    Image.fromarray(arr).save("hb.png")
    rs, hs = analyze(arr)
    print("player:", rs)
    print("hazards:", hs)