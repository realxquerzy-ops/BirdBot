"""
hypei_deco.py - generate "Hypei.gmd" from "Hypei Layout.gmd".

v11 - STRUCTURED PASS.  Rebuilt around the creator's actual block-design
recipe (from his tutorials) instead of a scattered motif dump.

His process (straight from the videos):
  structure  ->  base  ->  details (spikes + 3D)  ->  small adjustments

Block design recipe:
  * base is DARK
  * shadow line: copy the structure, move it diagonally, drop its z, black
  * lines = the background colour but a little brighter
  * 3D is LESS bright than the lines (contrast)
  * a black glow, very low opacity, on the BOTTOM
  * a really bright glow on the TOP  -> concentrates brightness to a focus
  * small, coherent details only (don't spam)
  * spikes: black outline + main colour + lighter inner + glow on top

Spike palette rule:
  color1 = main, color2 = lighter main, color3 = dark main, color4 = accent.
  Line & Obj copy color 1.  Blending ON for all glow.

Background rule:
  low-opacity, low-brightness BLENDING blocks arranged as a pattern (not a
  random scatter), duplicated up/right for a cheap parallax/blur, behind all.

Grid: centres are 15 + 30k.  Every added object is NO-HITBOX (121=1).
"""

import re, gzip, base64, math, random

SRC = r"C:\Users\Tsunami74\Downloads\Hypei Layout.gmd"
DST = r"C:\Users\Tsunami74\Downloads\Hypei.gmd"

# ---------------------------------------------------------------- container
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

def fnum(v):
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    if isinstance(v, int):
        return str(v)
    return ("%.3f" % float(v)).rstrip("0").rstrip(".")

def g30(v):
    return 15 + 30 * int(round((v - 15) / 30.0))

def gfloor30(v):
    return 15 + 30 * int(math.floor((v - 15) / 30.0))

# ---------------------------------------------------------------- kS38 colours
def _chan_dict(ch):
    f = ch.split("_")
    return {f[i]: f[i + 1] for i in range(0, len(f) - 1, 2)}, f

def parse_channels(header):
    m = re.search(r"kS38,(.*?)(?=,kA13|,kS39|$)", header)
    out = []
    if not m:
        return out
    for ch in m.group(1).split("|"):
        if not ch:
            continue
        d, _ = _chan_dict(ch)
        out.append((d.get("6"), (d.get("1"), d.get("2"), d.get("3")), ch))
    return out

def channel_str(cid, r, g, b, template, blend=None, opacity=None):
    d, f = _chan_dict(template)
    d["1"], d["2"], d["3"], d["6"] = str(r), str(g), str(b), str(cid)
    if blend is not None:
        d["18"] = str(blend)
    if opacity is not None:
        d["7"] = fnum(opacity)
    order = f[::2]
    return "_".join("%s_%s" % (k, d[k]) for k in order)

def add_channels(header, channels, template):
    m = re.search(r"(kS38,)(.*?)(,kA13|,kS39|$)", header)
    ks38 = m.group(2)
    extra = "".join("|" + channel_str(cid, r, g, b, template, blend, op)
                    for cid, (r, g, b), blend, op, _ in channels)
    if not ks38.endswith("|"):
        ks38 = ks38 + "|"
    ks38 = ks38 + extra.lstrip("|")
    return header[:m.start(2)] + ks38 + header[m.end(2):]

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

# ---------------------------------------------------------------- vocabulary
SQ      = 211    # Colored Inner Square  (block fill)
SQ2     = 207    # Colored Square        (block face / detail)
OUTL    = 467    # Outline Square        (block border)
OUTL_C  = 469    # Outline Outer Corner
OUTL_T  = 468    # Outline Top
DL3     = 507    # 3DL Top Middle        (depth lip)
GLOW    = 503    # Straight Medium Glow
CROSS   = 1765   # Tiny Cross
MECH    = 281    # Transparent Colored Mechanical Square (block texture - panel)
GRID    = 280    # Transparent Colored Grid Patterned Square (block texture - grid)
BEVEL   = 282    # Transparent Colored Beveled Square
BRICK   = 1266   # Large Beveled Bricks (block texture - bricks)
LTBRICK = 233    # Decorative Light Bricks
DIAG    = 182    # Small Cartwheel
CIRC    = 3637   # Large Circle
HOLLOW  = 3622   # Hollow Circle
SPIKEH  = 217    # Colored Half Spike
SPIKE   = 216    # Colored Spike
ARROW   = 3893   # Simple Arrow Particle
STAR_S  = 3884   # Small Four Point Star Particle
STAR_M  = 3883   # Medium Four Point Star Particle
GEAR    = 1735   # Medium Gear Blade
NAIL    = 435    # (soft dot)
TRI     = 3628   # Triangle (mountains)
CLOUD_L = 222    # Large Round Cloud
CLOUD_M = 223    # Medium Round Cloud
CLOUD_S = 224    # Small Round Cloud
STAR    = 3625   # Star

BLOCKY = {1, 2, 3, 4}
SPIKES = {8, 39, 103}
PORTS  = {10, 11, 12, 13, 47, 99, 101, 111, 1933, 745}
ORBS   = {35, 36, 67, 84, 140, 141, 1022, 1333, 1704, 1751, 3004}
SPEED_PORTAL = {200: 251.16, 201: 311.58, 202: 387.42, 203: 468.0}

# background parallax groups (assigned via object key 57) + screen-speed
# factor f (1.0 = static / full speed, 0.0 = pinned to screen).  Farther
# layers get a smaller f so they drift less -> depth.
P_SKY, P_SUN, P_STARS, P_CLOUD = 201, 202, 203, 204
P_MTN_FAR, P_MTN_MID, P_MTN_NEAR, P_MTN_FRONT = 205, 206, 207, 208
F_SKY, F_SUN, F_STARS, F_CLOUD = 0.15, 0.15, 0.10, 0.45
F_MTN_FAR, F_MTN_MID, F_MTN_NEAR, F_MTN_FRONT = 0.60, 0.75, 0.88, 1.00
PARALLAX = [(P_SUN, F_SUN), (P_SKY, F_SKY), (P_STARS, F_STARS),
            (P_CLOUD, F_CLOUD), (P_MTN_FAR, F_MTN_FAR),
            (P_MTN_MID, F_MTN_MID), (P_MTN_NEAR, F_MTN_NEAR)]
            # P_MTN_FRONT stays static (no trigger)

# ---------------------------------------------------------------- palette
# ORIGINAL cool "indigo twilight" scheme (NOT Kumomi's warm peach/cream).
# Solids are cool slate-indigo; lines are pale cyan; accents aqua / magenta.
C_DARK   = 1020   # (36,44,72)     block base  (deep indigo-slate)
C_BROWN  = 1021   # (58,74,112)    base detail (lighter slate blue)
C_3D     = 1022   # (74,96,140)    3D - LESS bright than lines
C_LINE   = 1023   # (186,232,244)  line = bg brighter (pale cyan)
C_LINE2  = 1024   # (228,248,252)  brighter line / spike inner
C_YELLOW = 1025   # (120,255,224)  accent A (aqua-mint)
C_SALMON = 1026   # (255,140,220)  accent B (magenta-pink)
C_BLUEGRAY = 1027 # (110,150,220)  accent C (periwinkle)
C_BLACK  = 1028   # (0,0,0)
# glows (blend 1)
G_LINE   = 1030   # (150,230,255)  bright glow  (top focus)  cyan
G_ACCENT = 1031   # (200,160,255)  accent glow  (spikes / air) violet
G_DARK   = 1032   # (8,10,18)      black glow   (bottom contrast)
# --- twilight art-background channels ---
SUN      = 1040   # (210,255,250)  pale aqua sun
SUN_GLOW = 1041   # (120,230,220)  blend aqua glow
MTN_FAR  = 1042   # (110,96,168)   violet far
MTN_MID  = 1043   # (78,70,132)    deeper violet
MTN_NEAR = 1044   # (50,50,96)     indigo
MTN_FRONT= 1045   # (28,30,60)     dark indigo
CLOUD_HI = 1046   # (170,200,240)  cool light cloud
CLOUD_LO = 1047   # (130,150,210)  cooler cloud
CLOUD_SH = 1048   # (70,80,130)    cloud shadow
SKY_BASE = 1060   # sky gradient band 0..NSKY-1  (1060..)
NSKY     = 18

def _lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))

# ORIGINAL twilight ramp: deep indigo -> violet -> magenta -> blue -> teal
# -> pale aqua  (cool scheme, deliberately not Kumomi's warm gold horizon)
SKY_STOPS = [(14, 16, 44), (32, 24, 76), (72, 38, 116), (120, 56, 130),
             (86, 84, 150), (48, 130, 168), (86, 194, 190), (176, 234, 220)]

def _ramp(stops, n):
    out = []
    for i in range(n):
        t = i / (n - 1.0) * (len(stops) - 1)
        k = min(int(t), len(stops) - 2)
        out.append(_lerp(stops[k], stops[k + 1], t - k))
    return out

SKY_RGB = _ramp(SKY_STOPS, NSKY)   # index 0 = top (dark), last = horizon (bright)

EXTRA = [
    (C_DARK,     (36, 44, 72),   0, 1.0),
    (C_BROWN,    (58, 74, 112),  0, 1.0),
    (C_3D,       (74, 96, 140),  0, 1.0),
    (C_LINE,     (186, 232, 244), 0, 1.0),
    (C_LINE2,    (228, 248, 252), 0, 1.0),
    (C_YELLOW,   (120, 255, 224), 0, 1.0),
    (C_SALMON,   (255, 140, 220), 0, 1.0),
    (C_BLUEGRAY, (110, 150, 220), 0, 1.0),
    (C_BLACK,    (0, 0, 0),      0, 1.0),
    (G_LINE,     (150, 230, 255), 1, 0.6),
    (G_ACCENT,   (200, 160, 255), 1, 0.6),
    (G_DARK,     (8, 10, 18),    1, 0.35),
    (SUN,        (210, 255, 250), 0, 1.0),
    (SUN_GLOW,   (120, 230, 220), 1, 0.45),
    (MTN_FAR,    (110, 96, 168), 0, 1.0),
    (MTN_MID,    (78, 70, 132),  0, 1.0),
    (MTN_NEAR,   (50, 50, 96),   0, 1.0),
    (MTN_FRONT,  (28, 30, 60),   0, 1.0),
    (CLOUD_HI,   (170, 200, 240), 0, 1.0),
    (CLOUD_LO,   (130, 150, 210), 0, 1.0),
    (CLOUD_SH,   (70, 80, 130),  1, 0.6),
] + [(SKY_BASE + i, SKY_RGB[i], 0, 1.0) for i in range(NSKY)]
ACCENTS = [C_YELLOW, C_SALMON, C_BLUEGRAY, C_LINE2]

def acc_chan(x):
    return ACCENTS[int(x // 900.0) % len(ACCENTS)]

# ---------------------------------------------------------------- x(t) mapping
def build_time_map(objs):
    portals = sorted(((o["x"], o["id"]) for o in objs if o["id"] in SPEED_PORTAL), key=lambda t: t[0])
    maxx = max(o["x"] for o in objs) + 2000
    cur = SPEED_PORTAL[201]
    prev = 0.0
    segs = []
    for x, pid in portals:
        if x <= 30:
            cur = SPEED_PORTAL[pid]
            continue
        segs.append((prev, cur))
        cur = SPEED_PORTAL[pid]
        prev = x
    segs.append((prev, cur))
    times = [0.0]
    for i in range(1, len(segs)):
        x0, sp = segs[i - 1]
        times.append(times[-1] + (segs[i][0] - x0) / sp)

    def x_of(t):
        if t <= 0:
            return 0.0
        for i in range(len(segs)):
            t0, (x0, sp) = times[i], segs[i]
            x1 = segs[i + 1][0] if i + 1 < len(segs) else maxx + 1e6
            t1 = t0 + (x1 - x0) / sp
            if t <= t1:
                return x0 + (t - t0) * sp
        return 0.0
    return x_of


def segments(objs, x_end):
    """Split the level into (x_start, x_end, speed) runs between speed portals,
    merging consecutive runs that share a speed.  Used to drive parallax."""
    portals = sorted(((o["x"], o["id"]) for o in objs if o["id"] in SPEED_PORTAL),
                     key=lambda t: t[0])
    cur = SPEED_PORTAL[201]
    prev = 0.0
    raw = []
    for x, pid in portals:
        if x <= 30:
            cur = SPEED_PORTAL[pid]
            continue
        raw.append((prev, x, cur))
        cur = SPEED_PORTAL[pid]
        prev = x
    raw.append((prev, x_end, cur))
    out = []
    for s in raw:
        if out and abs(out[-1][2] - s[2]) < 1e-6 and abs(out[-1][1] - s[0]) < 1e-6:
            out[-1] = (out[-1][0], s[1], s[2])
        else:
            out.append(s)
    return [s for s in out if s[1] > s[0]]


# ---------------------------------------------------------------- generation
def generate(objs):
    added = []
    xs = [o["x"] for o in objs]
    minx, maxx = min(xs), max(xs)

    def emit(id_, x, y, color, zlayer, zo, rot=0.0, sx=1.0, sy=1.0, extra=None):
        d = [("1", id_), ("2", fnum(x)), ("3", fnum(y)), ("21", color),
             ("25", zo), ("128", fnum(sx)), ("129", fnum(sy))]
        if rot:
            d.append(("6", fnum(rot)))
        if zlayer is not None:
            d.append(("24", zlayer))
        if extra:
            for k, v in extra.items():
                d.append((k, fnum(v) if isinstance(v, (int, float)) else v))
        d.append(("121", 1))
        added.append(",".join("%s,%s" % (k, v) for k, v in d))

    # triggers: position + the standard trigger metadata + their own keys
    def trig(id_, x, y, kv):
        d = [("1", id_), ("2", fnum(x)), ("3", fnum(y)),
             ("96", 1), ("64", 1), ("67", 1), ("116", 1), ("507", 1),
             ("155", 5), ("34", 1), ("36", 1)]
        for k, v in kv:
            d.append((k, fnum(v) if isinstance(v, (int, float)) else v))
        added.append(",".join("%s,%s" % (k, v) for k, v in d))

    # ------- the block-design recipe (mechanical/grid + glow frame) -----
    # Inspired by the reference "block designs .gmd": the WHOLE block mass is
    # framed (bright outline + glow on EXPOSED edges only) while the interior
    # is tiled with transparent mechanical / grid squares for texture, so a run
    # of blocks reads as ONE coherent shape instead of a grid of little frames.
    def cell(x, y, exp):
        # texture: opaque base (hides the raw black gameplay block) + two
        # transparent patterned squares layered on top -> panel/grid texture
        emit(SQ, x, y, C_DARK, None, 1, 0, 1.02, 1.02)
        emit(MECH, x, y, C_BROWN, None, 2, 0, 1.0, 1.0)
        emit(GRID, x, y, C_3D, None, 3, 0, 1.0, 1.0)
        # silhouette frame: bright line + glow, EXPOSED edges only
        if "N" in exp:
            emit(OUTL_T, x, y + 15, C_LINE, None, 10, 0, 1.0, 1.0)
            emit(GLOW, x, y + 15, G_LINE, None, 11, 0, 1.0, 0.55)
        if "S" in exp:
            emit(OUTL_T, x, y - 15, C_LINE, None, 10, 180, 1.0, 1.0)
            emit(GLOW, x, y - 15, G_DARK, None, 11, 0, 1.0, 0.55)
        if "E" in exp:
            emit(OUTL_T, x + 15, y, C_LINE, None, 10, 270, 1.0, 1.0)
            emit(GLOW, x + 15, y, G_LINE, None, 11, 90, 1.0, 0.55)
        if "W" in exp:
            emit(OUTL_T, x - 15, y, C_LINE, None, 10, 90, 1.0, 1.0)
            emit(GLOW, x - 15, y, G_LINE, None, 11, 90, 1.0, 0.55)

    def spike(x, y, rot, fx, fy, accent):
        e = {}
        if fx:
            e["4"] = 1
        if fy:
            e["5"] = 1
        emit(SPIKEH, x, y, C_BLACK, None, 0, rot, 1.15, 1.15, e)   # black outline
        emit(SPIKEH, x, y, accent, None, 1, rot, 1.0, 1.0, e)      # main colour
        emit(SPIKEH, x, y, C_LINE2, None, 2, rot, 0.55, 0.55, e)   # lighter inner
        emit(GLOW, x, y, G_ACCENT, None, 3, rot, 0.6, 0.6)         # glow on top

    # ================= SUNSET LANDSCAPE ART BACKGROUND =================
    # All bg objects live at strongly negative z so gameplay blocks sit in
    # front.  A sun sets behind layered mountains, warm clouds drift above.
    rng = random.Random(11)
    # the gameplay ground sits around y~300, so ridge bases belong THERE (not
    # at y40) and peaks must clear the block line (~420) to be visible behind it
    HORIZON = 300.0
    XT = maxx - minx

    def xhi(f):
        # a layer moving at screen-speed factor f sits at world X ~ f*c (it
        # lags the camera by (1-f)*c).  Since c never exceeds maxx, only tiles
        # with X <= f*maxx (+ margin) ever enter view - tiling further right
        # would put objects permanently off-screen.
        return f * maxx + 900

    def art_bg():
        # NEVER stretch one sprite across the level: heavy scaling breaks
        # rendering and pixelates textures.  Bands/ridges are tiled from many
        # normal-sized objects instead (scale kept small on purpose).
        TW = 240.0                      # tile width -> scale 8 (was 60!)
        # 1. sky gradient : bands from bright horizon up to deep dusk
        sky_bottom, sky_top = 18.0, 900.0
        bh = (sky_top - sky_bottom) / NSKY
        for i in range(NSKY):
            yc = sky_top - (i + 0.5) * bh
            chan = SKY_BASE + i
            xt = gfloor30(minx - 900)
            while xt < xhi(F_SKY):
                emit(SQ, xt, yc, chan, None, -500, 0, TW / 30.0,
                     bh / 30.0 + 0.12, {"57": P_SKY})
                xt += TW

        # 2. sun + halo, hanging low in the sky above the ridges
        x = gfloor30(minx) + 900
        while x < xhi(F_SUN):
            emit(CIRC, x, 500, SUN_GLOW, None, -495, 0, 6.0, 6.0, {"57": P_SUN})
            emit(CIRC, x, 500, SUN, None, -493, 0, 3.2, 3.2, {"57": P_SUN})
            x += 3600

        # 3. mountain ranges - 4 depth layers of small overlapping triangles.
        #    Peaks sized to sit in view above the block line (~y420) without
        #    clipping the top; scale still capped (~<=9x) to stay crisp.
        layers = [
            (MTN_FAR,   -470, 220.0, 1.2,  P_MTN_FAR,  0.60),
            (MTN_MID,   -466, 175.0, 1.15, P_MTN_MID,  0.75),
            (MTN_NEAR,  -462, 130.0, 1.1,  P_MTN_NEAR, 0.88),
            (MTN_FRONT, -458, 90.0,  1.0,  None,       1.00),
        ]
        for chan, z, maxh, ratio, grp, f in layers:
            x = minx - 200
            while x < xhi(f):
                h = maxh * (0.40 + 0.80 * rng.random())
                w = h * ratio
                emit(TRI, x, HORIZON + h / 2.0, chan, None, z, 0, w / 30.0,
                     h / 30.0, {"57": grp} if grp else None)
                x += w * (0.42 + 0.5 * rng.random())

        # 4. cool haze band hugging the horizon (depth, rides with the sky)
        xt = gfloor30(minx - 600)
        while xt < xhi(F_SKY):
            emit(SQ, xt, HORIZON + 30, SUN_GLOW, None, -455, 0, TW / 30.0,
                 1.6, {"57": P_SKY})
            xt += TW

        # 5. two cloud layers drifting over the ridges (cool top, shaded base)
        for chan, z, ylo, yhi, sc in [(CLOUD_HI, -482, 500, 760, 1.1),
                                      (CLOUD_LO, -480, 440, 620, 0.8)]:
            x = minx
            while x < xhi(F_CLOUD):
                y = ylo + (yhi - ylo) * rng.random()
                s = (1.5 + rng.random() * 1.7) * sc
                emit(CLOUD_SH, x, y - 6, CLOUD_SH, None, z - 2, 0, s * 1.9,
                     s * 0.6, {"57": P_CLOUD})
                emit(CLOUD_M, x, y, chan, None, z, 0, s * 1.8, s * 0.6,
                     {"57": P_CLOUD})
                x += 420 + rng.random() * 620

        # 6. starfield: repeated same star -> speckled texture up in the dusk
        x = minx
        while x < xhi(F_STARS):
            y = 640 + rng.random() * 260
            s = 0.28 + rng.random() * 0.3
            emit(STAR, x, y, SUN, None, -492, 0, s, s, {"57": P_STARS})
            x += 150 + rng.random() * 260

    art_bg()

    # ================= PARALLAX MOVE TRIGGERS =================
    # One linear Move per speed segment per depth group.  During a segment the
    # camera advances (xe-xs) in (xe-xs)/sp seconds, so moving the layer RIGHT
    # by (1-f)*(xe-xs) over that duration makes it drift left at only f x the
    # camera speed -> exact parallax even through speed-portal changes.
    x_of = build_time_map(objs)
    segs = segments(objs, maxx)
    for grp, f in PARALLAX:
        for xs, xe, sp in segs:
            trig(901, max(xs, 15.0), 465,
                 [("51", grp), ("28", (1.0 - f) * (xe - xs)),
                  ("29", 0), ("10", (xe - xs) / sp), ("30", 0), ("85", 2)])

    # ---------- 2. ground silhouette : dark landmass under the horizon ----------
    # fills everything below HORIZON so no sky leaks under the ridges; tiled at
    # a modest scale rather than one stretched slab.  a thin cool edge on top.
    GW = 240.0
    for yc in (15 + 71.25, 15 + 213.75):        # two 142.5-tall rows -> y 15..300
        x = gfloor30(minx - 300)
        while x < maxx + 600:
            emit(SQ, x, yc, MTN_FRONT, None, -450, 0, GW / 30.0, 4.75)
            x += GW
    x = gfloor30(minx - 300)
    while x < maxx + 600:
        emit(SQ, x, HORIZON, SUN_GLOW, None, -449, 0, GW / 30.0, 0.35)
        x += GW

    # ---------- 3. air deco : bright + rhythmic (reads as intentional) ----------
    n = 0
    x = g30(gfloor30(minx) + 450)
    while x < maxx:
        cy = [660.0, 480.0, 780.0, 360.0][n % 4]
        a = acc_chan(x)
        if n % 4 == 0:
            emit(ARROW, x, cy, a, None, 30, [0, 90, 180, 270][n % 4], 1.0, 1.0)
            emit(GLOW, x, cy, G_ACCENT, None, 29, 0, 0.7, 0.7)
        elif n % 4 == 1:
            emit(STAR_M, x, cy, a, None, 30, 0, 0.9, 0.9)
            emit(GLOW, x, cy, G_ACCENT, None, 29, 0, 0.6, 0.6)
        elif n % 4 == 2:
            emit(HOLLOW, x, cy, C_LINE, None, 30, 0, 1.1, 1.1)
            emit(CIRC, x, cy, a, None, 29, 0, 0.7, 0.7)
        else:
            emit(GEAR, x, cy, a, None, 30, 0, 0.9, 0.9)
            emit(GLOW, x, cy, G_ACCENT, None, 29, 0, 0.5, 0.5)
        x += 600
        n += 1

    # glow lasers on the line (two glow objects, blending)
    x = gfloor30(minx) + 300
    while x < maxx:
        emit(GLOW, x, 465, G_ACCENT, None, 20, 0, 1.4, 0.4)
        emit(GLOW, x, 465, G_LINE, None, 21, 0, 0.8, 0.35)
        x += 1200

    # ---------- 4. gameplay re-skin (block + spike designs) ----------
    # exact block-centre set -> which silhouette edges are exposed (robust to
    # blocks that sit on the half grid, e.g. x = 30k instead of 15+30k)
    cells = set()
    for o in objs:
        if o["id"] in BLOCKY:
            cells.add((round(o["x"], 1), round(o["y"], 1)))
    for o in objs:
        oid, x, y = o["id"], o["x"], o["y"]
        rot = float(o.get("6", 0) or 0)
        fx = float(o.get("4", 0) or 0)
        fy = float(o.get("5", 0) or 0)
        sx = float(o.get("128", 1) or 1)
        sy = float(o.get("129", 1) or 1)
        accent = acc_chan(x)
        if oid in BLOCKY:
            exp = set()
            if (round(x, 1), round(y + 30, 1)) not in cells: exp.add("N")
            if (round(x, 1), round(y - 30, 1)) not in cells: exp.add("S")
            if (round(x + 30, 1), round(y, 1)) not in cells: exp.add("E")
            if (round(x - 30, 1), round(y, 1)) not in cells: exp.add("W")
            cell(x, y, exp)
        elif oid in SPIKES:
            spike(x, y, rot, fx, fy, accent)
        elif oid in PORTS:
            emit(CIRC, x, y, C_LINE, None, -20, 0, 1.4, 1.4)
            emit(HOLLOW, x, y, C_LINE2, None, -19, 0, 1.7, 1.7)
        elif oid in ORBS:
            emit(CIRC, x, y, C_YELLOW, None, -20, 0, 0.8, 0.8)
            emit(HOLLOW, x, y, C_LINE2, None, -19, 0, 1.0, 1.0)

    # ---------- 5. beat-synced pulses ----------
    beat = 60.0 / 176.0
    t = 0.0
    k = 0
    while x_of(t) <= maxx:
        px = x_of(t)
        rgb = (120, 235, 255) if k % 2 == 0 else (200, 150, 255)
        emit(1006, px, 465, 101, 0, 0, 0, 1, 1,
             {"36": 1, "52": 1, "51": 101, "45": 0.2, "46": 0.3, "47": 0.4, "210": 1,
              "7": rgb[0], "8": rgb[1], "9": rgb[2]})
        t += beat
        k += 1
    return added


def main():
    txt = read_container(SRC)
    old_k4 = get_k4(txt)
    header, objs = split_level(decode_level(old_k4))
    parsed = [parse_obj(o) for o in objs if re.match(r"^1,-?\d+", o)]
    print("original objects:", len(objs), " parsed:", len(parsed))

    header = set_channels(header, {
        "1000": (22, 28, 54),      # BG   deep indigo
        "1001": (90, 140, 220),    # G1   periwinkle
        "1009": (90, 140, 220),    # G2   periwinkle
        "1002": (186, 232, 244),   # Line pale cyan
        "1004": (186, 232, 244),   # Obj  (copy of line colour)
        "1003": (74, 96, 140),     # 3DL
        "1013": (60, 120, 190),    # MG
        "1014": (60, 120, 190),    # MG2
    })

    tpl = [c for c in parse_channels(header) if c[0] == "1004"]
    tpl = tpl[0][2] if tpl else "1_255_2_255_3_255_11_255_12_255_13_255_4_-1_6_1004_7_1_15_1_18_0_8_1"
    chans = [(c, rgb, blend, op, 1) for c, rgb, blend, op in EXTRA]
    header = add_channels(header, chans, tpl)

    added = generate(parsed)
    print("added deco objects:", len(added))

    new_level = header + ";" + ";".join(objs + added) + ";"
    new_k4 = encode_level(new_level)

    out = txt.replace("<k>k4</k><s>" + old_k4 + "</s>", "<k>k4</k><s>" + new_k4 + "</s>")
    out = out.replace("<k>k2</k><s>Hypei Layout</s>", "<k>k2</k><s>Hypei</s>")
    out = re.sub(r"<k>k48</k><i>\d+</i>", "<k>k48</k><i>%d</i>" % (len(objs) + len(added)), out)
    open(DST, "wb").write(out.encode("utf-8"))

    chk = read_container(DST)
    h2, o2 = split_level(decode_level(get_k4(chk)))
    print("VERIFY new objects:", len(o2), " originals intact:", o2[:len(objs)] == objs)
    print("VERIFY k2:", "<k>k2</k><s>Hypei</s>" in chk)
    print("wrote", DST, __import__("os").path.getsize(DST), "bytes")


if __name__ == "__main__":
    main()
