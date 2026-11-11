import sys
import numpy as np
from PIL import Image

path = sys.argv[1] if len(sys.argv) > 1 else "game_live.png"
COLS = int(sys.argv[2]) if len(sys.argv) > 2 else 120
crop = [int(x) for x in sys.argv[3:7]] if len(sys.argv) >= 7 else None
mode = sys.argv[7] if len(sys.argv) > 7 else "color"

img = Image.open(path).convert("RGB")
if crop:
    img = img.crop((crop[0], crop[1], crop[2], crop[3]))
W, H = img.size
rows = max(1, round(COLS * (H / W) / 2.0))

if mode == "bw":
    g = np.asarray(img.convert("L").resize((COLS, rows), Image.BILINEAR)).astype(float)
    print(f"{path} crop={crop} -> {COLS}x{rows} (bw)")
    for y in range(rows):
        print("".join("#" if g[y, x] > 110 else ("." if g[y, x] > 55 else " ") for x in range(COLS)))
    sys.exit()

small = np.asarray(img.resize((COLS, rows), Image.BILINEAR)).astype(float)
r, g, b = small[..., 0], small[..., 1], small[..., 2]
mx = small.max(2); mn = small.min(2); val = mx
sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0)
hue = np.zeros_like(mx); d = np.maximum(mx - mn, 1e-6)
m = (mx == r); hue[m] = (60 * ((g - b) / d) % 360)[m]
m = (mx == g); hue[m] = (60 * ((b - r) / d) + 120)[m]
m = (mx == b); hue[m] = (60 * ((r - g) / d) + 240)[m]

def classify(y, x):
    v = val[y, x]; s = sat[y, x]; h = hue[y, x]
    if v < 35: return ' '
    if v < 70 and s < 0.25: return '.'
    if s < 0.18: return 'W' if v > 200 else ('=' if v > 90 else ':')
    if s < 0.45 and v < 120: return ','
    if h < 20 or h >= 330: return 'r'
    if h < 45: return 'o'
    if h < 70: return 'y'
    if h < 160: return 'g'
    if h < 200: return 'c'
    if h < 260: return 'b'
    return 'm'

print(f"{path} crop={crop} -> {COLS}x{rows}")
for y in range(rows):
    print("".join(classify(y, x) for x in range(COLS)))
