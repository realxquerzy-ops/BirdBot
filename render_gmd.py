"""
render_gmd.py - render a .gmd level to (a) an ASCII density/brightness map that
the agent can READ as text, (b) PNG images for the user, and (c) numeric metrics.

Usage (as a library):
    L = load_level(path)
    print(ascii_map(L, cols=140, rows=28))
    print(metrics(L))
    render_png(L, "out.png", x0=None, x1=None, scale=0.10)

Usage (CLI):
    python render_gmd.py <level.gmd> [--png out.png] [--cols 140] [--rows 28]
                         [--x0 N --x1 N] [--scale 0.10]
"""
import re, gzip, base64, math, csv, os, sys
import numpy as np
from PIL import Image, ImageDraw

NAMES = {}
_csv = r"C:\Users\TSUNAM~1\AppData\Local\Temp\opencode\objects.csv"
if os.path.exists(_csv):
    with open(_csv, encoding="utf-8", errors="replace") as f:
        for row in csv.reader(f):
            if len(row) > 1 and row[0].strip().isdigit():
                NAMES[int(row[0])] = row[1].strip()

TRIGGER_IDS = {899, 901, 1006, 1007, 1011, 1012, 1268, 1334, 1346, 1347, 1520,
               1543, 1616, 1811, 1815, 1817, 1913, 1914, 1915, 1916, 1917, 1918,
               1931, 1932, 1933, 1934, 1935, 2865, 2866, 2867, 2875, 2876, 2877,
               2899, 2900, 2901, 2902, 2903, 2904, 2905, 2911, 2912, 2913, 2915,
               2916, 2917, 2918, 2919, 2920, 2921, 2922, 2923, 2924, 2925, 2926,
               2927, 2928, 2929, 2930, 2931, 2932, 2933, 2934, 2935, 2936, 2937,
               2938, 2939, 2940, 2941, 2942, 2943, 2944, 2945, 2946, 2947, 2948,
               2949, 2950, 2951, 2952, 2953, 2954, 2955, 3006, 3007, 3008, 3009,
               3010, 3011, 3012, 3013, 3014, 3015, 3016, 3017, 3018, 3019, 3020,
               3021, 3022, 3023, 3024, 3025, 3026, 3027, 3028, 3029, 3030, 3031,
               3032, 3033, 3034, 3035, 3036, 3037, 3038, 3039, 3040, 3041, 3042,
               3043, 3044, 3045, 3046, 3047, 3048, 3049, 3050, 3051, 3052, 3053,
               3054, 3055, 3056, 3057, 3058, 3059, 3060, 3061, 3062, 3063, 3064,
               3065, 3066, 3067, 3068, 3069, 3070, 3071, 3072, 3073, 3074, 3075,
               3076, 3077, 3078, 3079, 3080, 3081, 3082, 3083, 3084, 3085, 3086,
               3087, 3088, 3089, 3090, 3091, 3092, 3093, 3094, 3095, 3096, 3097,
               3098, 3099, 3100, 3101, 3102, 3103, 3104, 3105, 3106, 3107, 3108,
               3109, 3110, 3111, 3112, 3113, 3114, 3115, 3116, 3117, 3118, 3119,
               3120, 3121, 3122, 3123, 3124, 3125, 3126, 3127, 3128, 3129, 3130,
               3131, 3132, 3133, 3134, 3135, 3136, 3137, 3138, 3139, 3140, 3141,
               3142, 3143, 3144, 3145, 3146, 3147, 3148, 3149, 3150}
TEXT_IDS = {914}
EDGE_IDS = {468, 470, 471}   # Outline Top / pillars -> thin bar on one edge


def read_container(path):
    return open(path, "rb").read().decode("utf-8", "replace")


def get_k4(txt):
    return re.search(r"<k>k4</k><s>(.*?)</s>", txt, re.S).group(1)


def decode_level(b64):
    return gzip.decompress(base64.urlsafe_b64decode(b64 + "=" * (-len(b64) % 4))).decode("utf-8", "replace")


def encode_level(level):
    return base64.urlsafe_b64encode(gzip.compress(level.encode("utf-8"), 9, mtime=0)).decode("ascii")


def split_level(level):
    parts = level.split(";")
    objs = parts[1:]
    if objs and objs[-1] == "":
        objs = objs[:-1]
    return parts[0], objs


def parse_obj(s):
    t = s.split(",")
    o = {"id": int(t[1]), "x": float(t[3]), "y": float(t[5])}
    for i in range(6, len(t) - 1, 2):
        o[t[i]] = t[i + 1]
    return o


def _chan_dict(ch):
    f = ch.split("_")
    return {f[i]: f[i + 1] for i in range(0, len(f) - 1, 2)}, f


def set_channels(header, changes):
    m = re.search(r"(kS38,)(.*?)(,kA13|,kS39|$)", header)
    entries = m.group(2).split("|")
    out = []
    for e in entries:
        if not e:
            out.append(e)
            continue
        d, f = _chan_dict(e)
        cid = d.get("6")
        if cid in changes:
            r, g, b = changes[cid]
            d["1"], d["2"], d["3"] = str(r), str(g), str(b)
            e = "_".join("%s_%s" % (k, d[k]) for k in f[::2])
        out.append(e)
    return header[:m.start(2)] + "|".join(out) + header[m.end(2):]


def parse_channels(header):
    """id -> dict with r,g,b,opacity,blend"""
    out = {}
    m = re.search(r"kS38,(.*?)(?=,kA13|,kS39|$)", header)
    if not m:
        return out
    for ch in m.group(1).split("|"):
        if not ch:
            continue
        f = ch.split("_")
        d = {f[i]: f[i + 1] for i in range(0, len(f) - 1, 2)}
        cid = d.get("6")
        if cid is None:
            continue
        out[cid] = {
            "r": int(float(d.get("1", 255))),
            "g": int(float(d.get("2", 255))),
            "b": int(float(d.get("3", 255))),
            "opacity": float(d.get("7", 1) or 1),
            "blend": d.get("18", "0"),
        }
    return out


class Level(object):
    def __init__(self, path):
        self.path = path
        txt = read_container(path)
        self.header, self.objs = split_level(decode_level(get_k4(txt)))
        self.parsed = [parse_obj(o) for o in self.objs if re.match(r"^1,-?\d+", o)]
        self.channels = parse_channels(self.header)
        self.minx = min(o["x"] for o in self.parsed)
        self.maxx = max(o["x"] for o in self.parsed)
        self.miny = min(o["y"] for o in self.parsed)
        self.maxy = max(o["y"] for o in self.parsed)


def resolve_color(o, channels, default=(128, 128, 128)):
    cid = o.get("21")
    if cid is not None and str(cid) in channels:
        c = channels[str(cid)]
        return (c["r"], c["g"], c["b"]), c["opacity"]
    # fall back to special defaults
    if o["id"] in TRIGGER_IDS:
        return (255, 0, 255), 0.0
    return default, 1.0


def classify(oid):
    name = NAMES.get(oid, "")
    n = name.lower()
    if oid in TRIGGER_IDS or "trigger" in n:
        return "trigger"
    if oid in TEXT_IDS or "text" in n:
        return "text"
    if "spike" in n or "blade" in n or "hazard" in n:
        return "spike"
    if "triangle" in n:
        return "triangle"
    if "circle" in n or "cloud" in n or "orb" in n or "dot" in n or "particle" in n or "star" in n:
        return "circle"
    if "glow" in n:
        return "glow"
    if "slope" in n or "quarter" in n or "arrow" in n:
        return "slope"
    if oid in EDGE_IDS:
        return "edge"
    if "outline" in n:
        return "outline"
    if "line" in n or "connector" in n or "arm" in n or "cross" in n or "cartwheel" in n or "gear" in n:
        return "line"
    return "square"


def obj_geom(o):
    cx, cy = o["x"], o["y"]
    sx = float(o.get("128", 1) or 1)
    sy = float(o.get("129", 1) or 1)
    rot = float(o.get("6", 0) or 0)
    fx = float(o.get("4", 0) or 1)
    fy = float(o.get("5", 0) or 1)
    return cx, cy, sx, sy, rot, fx, fy


def ascii_map(L, cols=140, rows=28, route=None):
    """Brightness grid as text. route = list of (x,y) gameplay points."""
    pad = 60
    x0, x1 = L.minx - pad, L.maxx + pad
    y0, y1 = L.miny - pad, L.maxy + pad
    gx = np.zeros((rows, cols), dtype=np.float64)
    gc = np.zeros((rows, cols), dtype=np.float64)
    rr = np.zeros((rows, cols), dtype=np.float64)
    gg = np.zeros((rows, cols), dtype=np.float64)
    bb = np.zeros((rows, cols), dtype=np.float64)

    dx = (x1 - x0) / cols
    dy = (y1 - y0) / rows
    for o in L.parsed:
        kind = classify(o["id"])
        if kind in ("trigger", "text"):
            continue
        (r, g, b), op = resolve_color(o, L.channels)
        cx, cy, sx, sy, rot, fx, fy = obj_geom(o)
        hw = 15 * sx
        hh = 15 * sy
        # approximate footprint as axis-aligned bbox (rotation widens it)
        rad = math.radians(rot)
        ext_x = abs(hw * math.cos(rad)) + abs(hh * math.sin(rad))
        ext_y = abs(hw * math.sin(rad)) + abs(hh * math.cos(rad))
        if kind == "circle" or kind == "glow":
            pass  # already roughly square footprint
        # brightness weight
        lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
        weight = op * (0.4 + 0.6 * lum)
        # cover cells
        cx0 = int((cx - ext_x - x0) / dx)
        cx1 = int((cx + ext_x - x0) / dx)
        cy0 = int((y1 - (cy + ext_y)) / dy)
        cy1 = int((y1 - (cy - ext_y)) / dy)
        for yy in range(max(0, cy0), min(rows, cy1 + 1)):
            for xx in range(max(0, cx0), min(cols, cx1 + 1)):
                gx[yy, xx] += weight
                gc[yy, xx] += 1
                rr[yy, xx] += r * op
                gg[yy, xx] += g * op
                bb[yy, xx] += b * op

    ramp = " .:-=+*#%@"
    # density-normalised brightness, then percentile-scaled for contrast
    val = np.zeros_like(gx)
    nz = gc > 0
    val[nz] = gx[nz] / np.sqrt(gc[nz])
    if val[nz].size:
        hi = np.percentile(val[nz], 97)
        if hi <= 0:
            hi = 1.0
    else:
        hi = 1.0
    lines = []
    header = "x:%.0f..%.0f  y:%.0f..%.0f  (each col=%.0fu, row=%.0fu)" % (
        x0, x1, y0, y1, dx, dy)
    lines.append(header)
    top = "    " + "".join(str(int((x0 + i * dx) // 1000) % 10) for i in range(cols))
    lines.append(top)
    for yy in range(rows):
        rowchars = []
        for xx in range(cols):
            v = val[yy, xx] / hi
            idx = int(min(len(ramp) - 1, max(0, v * (len(ramp) - 1) + 0.5)))
            rowchars.append(ramp[idx])
        lines.append("%3d|" % int(y1 - (yy + 0.5) * dy) + "".join(rowchars))
    return "\n".join(lines)


def hue_map(L, cols=140, rows=28):
    """Dominant-hue letters per cell: R/O/Y/G/C/B/P/W/D=dark."""
    pad = 60
    x0, x1 = L.minx - pad, L.maxx + pad
    y0, y1 = L.miny - pad, L.maxy + pad
    dx = (x1 - x0) / cols
    dy = (y1 - y0) / rows
    rr = np.zeros((rows, cols)); gg = np.zeros((rows, cols)); bb = np.zeros((rows, cols))
    cnt = np.zeros((rows, cols))
    for o in L.parsed:
        if classify(o["id"]) in ("trigger", "text"):
            continue
        (r, g, b), op = resolve_color(o, L.channels)
        cx, cy, sx, sy, rot, fx, fy = obj_geom(o)
        ext = 15 * max(sx, sy)
        cx0 = int((cx - ext - x0) / dx); cx1 = int((cx + ext - x0) / dx)
        cy0 = int((y1 - (cy + ext)) / dy); cy1 = int((y1 - (cy - ext)) / dy)
        for yy in range(max(0, cy0), min(rows, cy1 + 1)):
            for xx in range(max(0, cx0), min(cols, cx1 + 1)):
                rr[yy, xx] += r * op; gg[yy, xx] += g * op; bb[yy, xx] += b * op
                cnt[yy, xx] += op
    def hue_letter(r, g, b):
        mx = max(r, g, b); mn = min(r, g, b)
        if mx < 40:
            return "D"
        sat = (mx - mn) / float(mx)
        if sat < 0.22:
            return "W" if mx > 180 else "G"
        if r == mx:
            if g > 0.66 * r:
                return "Y" if g > 0.85 * r else "O"
            return "R" if b < g else "P"
        if g == mx:
            if b > 0.7 * g and r < 0.7 * g:
                return "C"
            if r > 0.7 * g:
                return "Y"
            return "G"
        # b == mx
        if r > 0.6 * b and g > 0.6 * b:
            return "P"
        if g > 0.55 * b:
            return "C"
        return "B"
    lines = []
    for yy in range(rows):
        row = []
        for xx in range(cols):
            if cnt[yy, xx] == 0:
                row.append(" ")
            else:
                row.append(hue_letter(rr[yy, xx]/cnt[yy, xx], gg[yy, xx]/cnt[yy, xx], bb[yy, xx]/cnt[yy, xx]))
        lines.append("%3d|" % int(y1 - (yy + 0.5) * dy) + "".join(row))
    return "\n".join(lines)


def metrics(L, route=None):
    """coverage / brightness / overlap stats."""
    pad = 60
    x0, x1 = L.minx - pad, L.maxx + pad
    y0, y1 = L.miny - pad, L.maxy + pad
    cols, rows = 200, 40
    dx = (x1 - x0) / cols; dy = (y1 - y0) / rows
    occ = np.zeros((rows, cols))
    lumsum = 0.0; n = 0
    for o in L.parsed:
        if classify(o["id"]) in ("trigger", "text"):
            continue
        (r, g, b), op = resolve_color(o, L.channels)
        cx, cy, sx, sy, rot, fx, fy = obj_geom(o)
        ext = 15 * max(sx, sy)
        lum = (0.299*r + 0.587*g + 0.114*b) / 255.0
        lumsum += lum * op; n += op
        cx0 = int((cx - ext - x0)/dx); cx1 = int((cx + ext - x0)/dx)
        cy0 = int((y1 - (cy + ext))/dy); cy1 = int((y1 - (cy - ext))/dy)
        for yy in range(max(0, cy0), min(rows, cy1+1)):
            for xx in range(max(0, cx0), min(cols, cx1+1)):
                occ[yy, xx] += 1
    coverage = float((occ > 0).sum()) / (rows * cols)
    out = {
        "objects": len(L.parsed),
        "minx": L.minx, "maxx": L.maxx, "miny": L.miny, "maxy": L.maxy,
        "coverage": round(coverage, 4),
        "mean_luminance": round(lumsum / max(1e-9, n), 4),
        "mean_objects_per_cell": round(float(occ.sum()) / (rows * cols), 2),
        "max_objects_per_cell": int(occ.max()),
    }
    # gameplay-route overlap: deco sitting near original solid blocks
    if route:
        blocks = [(o["x"], o["y"]) for o in L.parsed if o["id"] in (1,2,3,4,8,39,103)]
        deco = [(o["x"], o["y"]) for o in L.parsed if o["id"] not in (1,2,3,4,8,39,103)
                and classify(o["id"]) not in ("trigger","text")]
        if blocks and deco:
            bx = np.array([b[0] for b in blocks]); by = np.array([b[1] for b in blocks])
            dxp = np.array([d[0] for d in deco]); dyp = np.array([d[1] for d in deco])
            # crude: fraction of deco within 20u of a block centre
            close = 0
            for i in range(0, len(dxp), max(1, len(dxp)//2000)):
                dist = np.min((bx - dxp[i])**2 + (by - dyp[i])**2)
                if dist < 400:  # <20u
                    close += 1
            sample = len(range(0, len(dxp), max(1, len(dxp)//2000)))
            out["deco_near_route_frac"] = round(close / max(1, sample), 3)
    return out


def render_png(L, out_png, x0=None, x1=None, y0=None, y1=None, scale=0.10, bg=None):
    pad = 40
    if x0 is None: x0 = L.minx - pad
    if x1 is None: x1 = L.maxx + pad
    if y0 is None: y0 = L.miny - pad
    if y1 is None: y1 = L.maxy + pad
    if bg is None:
        c = L.channels.get("1000")
        bg = (c["r"], c["g"], c["b"]) if c else (12, 12, 14)
    W = max(1, int((x1 - x0) * scale))
    H = max(1, int((y1 - y0) * scale))
    base = Image.new("RGB", (W, H), bg)
    img = base.convert("RGBA")
    d = ImageDraw.Draw(img, "RGBA")
    order = sorted(L.parsed, key=lambda o: (int(o.get("24", 0) or 0), int(o.get("25", 0) or 0)))
    for o in order:
        kind = classify(o["id"])
        if kind in ("trigger", "text"):
            continue
        (r, g, b), op = resolve_color(o, L.channels)
        if op <= 0.01:
            continue
        cx, cy, sx, sy, rot, fx, fy = obj_geom(o)
        if not (x0 - 100 <= cx <= x1 + 100 and y0 - 100 <= cy <= y1 + 100):
            continue
        hw = 15 * sx * scale
        hh = 15 * sy * scale
        px = (cx - x0) * scale
        py = (y1 - cy) * scale
        rad = math.radians(-rot)  # screen y is flipped
        def rp(lx, ly):
            rx = lx * math.cos(rad) - ly * math.sin(rad)
            ry = lx * math.sin(rad) + ly * math.cos(rad)
            return (px + rx, py + ry)
        col = (r, g, b, int(255 * min(1.0, op)))
        if kind == "circle" or kind == "glow":
            d.ellipse([px - hw, py - hh, px + hw, py + hh], fill=col)
        elif kind == "spike":
            d.polygon([rp(0, hh), rp(-hw, -hh), rp(hw, -hh)], fill=col)
        elif kind == "triangle":
            d.polygon([rp(0, hh), rp(-hw, -hh), rp(hw, -hh)], fill=col)
        elif kind == "slope":
            d.polygon([rp(-hw, hh), rp(hw, hh), rp(hw, -hh)], fill=col)
        elif kind == "line":
            d.rectangle([px - hw, py - max(hh, 1.2), px + hw, py + max(hh, 1.2)], fill=col)
        elif kind == "outline":
            t = max(1.0, 1.5 * scale)
            d.rectangle([px - hw, py - hh, px + hw, py + hh], outline=col, width=max(1, int(t)))
        elif kind == "edge":
            # thin bar centred on the object (rot 0 = horizontal), like the real
            # "Outline Top" object which is a bar placed right on the edge
            t = max(1.0, hh * 0.20)
            d.polygon([rp(-hw, t), rp(hw, t), rp(hw, -t), rp(-hw, -t)], fill=col)
        else:
            d.polygon([rp(-hw, -hh), rp(hw, -hh), rp(hw, hh), rp(-hw, hh)], fill=col)
    img.convert("RGB").save(out_png)
    return out_png, (W, H)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Tsunami74\Downloads\Hypei.gmd"
    L = Level(path)

    def argval(flag, default=None):
        if flag in sys.argv:
            return float(sys.argv[sys.argv.index(flag) + 1])
        return default

    x0 = argval("--x0"); x1 = argval("--x1"); y0 = argval("--y0"); y1 = argval("--y1")
    if x0 is not None or y0 is not None:
        L.minx = x0 if x0 is not None else L.minx
        L.maxx = x1 if x1 is not None else L.maxx
        L.miny = y0 if y0 is not None else L.miny
        L.maxy = y1 if y1 is not None else L.maxy
        L.parsed = [o for o in L.parsed
                    if L.minx - 30 <= o["x"] <= L.maxx + 30 and L.miny - 30 <= o["y"] <= L.maxy + 30]

    print("=== METRICS ===")
    print(metrics(L, route=True))
    print()
    print("=== ASCII BRIGHTNESS MAP ===")
    print(ascii_map(L, cols=140, rows=26))
    print()
    print("=== HUE MAP (R/O/Y/G/C/B/P/W/D) ===")
    print(hue_map(L, cols=140, rows=26))
    if "--png" in sys.argv:
        out = sys.argv[sys.argv.index("--png") + 1]
        sc = argval("--scale", 0.10)
        p, size = render_png(L, out, scale=sc)
        print("wrote", p, size)
