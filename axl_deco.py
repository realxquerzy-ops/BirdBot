"""
axl_deco.py - decorate the "AxlAxolotl Collab" structure level with a FIRE theme.

The level is built out of outline/structure pieces (468/471/469/...).  We DO NOT
touch gameplay or the structure shape: we keep every existing object, give the
structure a warm fire gradient + glow, and add a clean fiery background
(dark sky, ember glow, drifting sparks, fiery base).  Goal: readable, tidy,
"not a mess".
"""
import re, os, math, random, base64, gzip

import hypei_deco as H

SRC = r"C:\Users\Tsunami74\Downloads\AxlAxolotl Collab.gdlvl"
DST = r"C:\Users\Tsunami74\Downloads\AxlAxolotl Collab Deco.gdlvl"


def read_level_container(path):
    raw = open(path, "rb").read()
    s = raw.decode("utf-8", "replace").strip()
    if s.startswith("PD94") or s.startswith("<?xml"):
        return s
    # try gdlvl base64(gzip(xml))
    try:
        return gzip.decompress(base64.urlsafe_b64decode(raw + b"=" * (-len(raw) % 4))).decode("utf-8", "replace")
    except Exception:
        return H.read_container(path)


def write_gdlvl(path, xml):
    out = base64.urlsafe_b64encode(gzip.compress(xml.encode("utf-8"), 9, mtime=0))
    open(path, "wb").write(out)


def write_level_container(path, xml):
    if path.lower().endswith(".gdlvl"):
        # if existing gdlvl exists as template, merge into it to preserve 2.209 keys
        if os.path.exists(path):
            try:
                tpl = read_level_container(path)
                k4 = H.get_k4(xml)
                tpl = re.sub(r"(<k>k4</k><s>).*?(</s>)", lambda m: m.group(1) + k4 + m.group(2), tpl, count=1, flags=re.S)
                # update k48 if present
                m48 = re.search(r"(<k>k48</k><[si]>)(\d+)(</[si]>)", xml)
                if m48:
                    tpl = re.sub(r"(<k>k48</k><[si]>)(\d+)(</[si]>)", lambda mm: mm.group(1) + m48.group(2) + mm.group(3), tpl, count=1)
                write_gdlvl(path, tpl)
                return
            except Exception:
                pass
        write_gdlvl(path, xml)
        return
    open(path, "wb").write(xml.encode("utf-8"))

# ---- vocabulary -----------------------------------------------------------
# solid "Outline" blocks the level is built from (these ARE the gameplay block)
OUTLINE = {467, 468, 469, 470, 471, 472, 473, 661, 662, 664, 656, 1338, 1339}
SPIKES  = {8, 39, 103, 392, 1889, 1891, 1892}
HAZARD  = {1705, 1706, 1722}
GLOW    = 503      # Straight Medium Glow
GLOW_S  = 1292     # Straight Small Glow
SQ      = 211      # Colored Inner Square (flat coloured, non-solid)
TEX     = 280      # grid/texture patterned square (non-solid)
TEX2    = 281      # grid/texture patterned square (non-solid)
CIRC    = 3637     # Large Circle
STAR    = 3625
SPARK   = 3884     # Small Four Point Star Particle

# ---- fire palette ---------------------------------------------------------
# existing channels get repainted to fire tones
REPAINT = {
    "1000": (16, 5, 7),       # BG  near-black ember
    "1001": (255, 96, 22),    # G1  fire orange (glow lines)
    "1009": (255, 96, 22),    # G2
    "1002": (255, 176, 66),   # Line  warm flame
    "1004": (255, 122, 34),   # Obj / structure lines  -> fire (main)
    "1003": (150, 42, 16),    # 3DL  deep ember
    "1013": (206, 62, 20),    # MG
    "1014": (206, 62, 20),    # MG2
    "1010": (255, 206, 96),   # highlight
}

# new channels  (GD colour channels are only valid up to 1014; play safe in the
# free low range 20-44 -- the level already uses 2 and 1000-1014)
CH_BG      = 20     # near-black base
CH_BAND0   = 21     # sky gradient bands 21..21+N-1 (top dark -> bottom hot)
N_BAND     = 8
CH_FIREGLW = 29     # broad fire glow (blend)
CH_DEEPRED = 30     # deep red wash (blend)
CH_EMBER   = 31     # ember/spark (blend)
CH_HOT     = 32     # hot core / lava (blend)
CH_GRAD0   = 33     # structure fire gradient 33..33+G-1
N_GRAD     = 12
CH_INNER   = 45     # dark interior fill (non-solid blocks inside the structures)
CH_INNER2  = 46     # slightly lighter interior accent
CH_EDGE    = 47     # bright edge highlight
CH_PULSE   = 48     # structure trim that PULSES warm on the beat
CH_PULSE_C = 49     # cool complementary accent that pulses on the downbeat
CH_DETAIL  = 50     # small dark rivet / detail
CH_PIPE    = 51     # dark warm metal pipe / rib detail

BPM = 175.0         # "Infernoplex" by Dimrain47 (song id 64842)

INNER_RGB  = (26, 8, 9)     # very dark ember interior
INNER2_RGB = (54, 16, 13)   # a touch lighter for variety
EDGE_RGB   = (255, 150, 50) # warm edge accent
RIVET_RGB  = (12, 4, 5)     # near-black rivet / detail dot
PIPE_RGB   = (92, 30, 14)   # dark warm metal (pipes / ribs)
PULSE_RGB  = (255, 96, 16)  # warm pulse BASE (brightens on beat)
PULSEC_RGB = (26, 78, 100)  # cool complementary BASE (brightens on beat)
COOL_RGB   = (70, 220, 255) # complementary cyan accent (pairs with the orange)

BG_RGB   = (10, 3, 4)
BAND_STOPS = [(10, 3, 4), (15, 5, 5), (22, 7, 7), (30, 9, 9),
              (40, 12, 11), (54, 16, 13), (70, 22, 15), (92, 30, 17)]
GRAD_STOPS = [(214, 46, 12), (255, 92, 20), (255, 138, 38), (255, 178, 66),
              (255, 214, 110), (255, 238, 156)]


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def ramp(stops, n):
    out = []
    for i in range(n):
        t = i / (n - 1.0) * (len(stops) - 1)
        k = min(int(t), len(stops) - 2)
        out.append(lerp(stops[k], stops[k + 1], t - k))
    return out


BAND_RGB = ramp(BAND_STOPS, N_BAND)     # 0 = dark top, last = hot bottom
GRAD_RGB = ramp(GRAD_STOPS, N_GRAD)     # 0 = deep red, last = bright yellow


def set_obj_color(s, chan):
    """add/replace key 21 (colour) on a raw object string, keep everything else"""
    t = s.split(",")
    head = t[:6]                     # 1,id 2,x 3,y
    pairs = []
    found = False
    i = 6
    while i < len(t) - 1:
        k, v = t[i], t[i + 1]
        if k == "21":
            pairs.append(("21", str(chan)))
            found = True
        else:
            pairs.append((k, v))
        i += 2
    if not found:
        pairs.append(("21", str(chan)))
    return ",".join(head + ["%s,%s" % (k, v) for k, v in pairs])


def generate(objs, minx, maxx, miny, maxy, parsed=None):
    added = []

    def emit(id_, x, y, color, zlayer, zo, rot=0.0, sx=1.0, sy=1.0, extra=None):
        d = [("1", id_), ("2", H.fnum(x)), ("3", H.fnum(y)), ("21", color),
             ("24", zlayer), ("25", zo), ("128", H.fnum(sx)), ("129", H.fnum(sy))]
        if rot:
            d.append(("6", H.fnum(rot)))
        if extra:
            for k, v in extra.items():
                d.append((k, H.fnum(v) if isinstance(v, (int, float)) else v))
        d.append(("121", 1))
        added.append(",".join("%s,%s" % (k, v) for k, v in d))

    rng = random.Random(7)
    # ---------------- background ----------------
    # key 24 = z-layer (B4=-3 back ... T16=15 front), key 25 = z-order within layer.
    # backgrounds must sit on a BACK z-layer or GD draws them in the void/white.
    TW = 240.0
    ylo, yhi = 0.0, 1100.0
    bh = (yhi - ylo) / N_BAND
    for i in range(N_BAND):
        yc = ylo + (i + 0.5) * bh
        x = H.gfloor30(minx - 600)
        while x < maxx + 600:
            emit(SQ, x, yc, CH_BAND0 + i, -3, 0, 0.0,
                 TW / 30.0 + 0.05, bh / 30.0 + 0.3)
            x += TW

    # fiery glow rising from the bottom of the playfield
    x = H.gfloor30(minx - 600)
    while x < maxx + 600:
        emit(SQ, x, 150, CH_FIREGLW, -2, 0, 0.0, TW / 30.0, 5.0)
        x += TW
    x = H.gfloor30(minx - 600)
    while x < maxx + 600:
        emit(SQ, x, 300, CH_DEEPRED, -2, 1, 0.0, TW / 30.0, 3.0)
        x += TW

    # drifting embers
    x = minx
    while x < maxx + 400:
        y = 150 + rng.random() * (maxy - 150)
        s = 0.25 + rng.random() * 0.5
        emit(SPARK, x, y, CH_EMBER, -1, 0, 0.0, s, s)
        if rng.random() < 0.5:
            emit(CIRC, x + 40, y - 30, CH_EMBER, -1, 1, 0.0, s * 2.0, s * 2.0)
        x += 150 + rng.random() * 260

    # ---- fill each structure (cluster of Outline blocks) with non-solid blocks
    # An "Outline" block only draws its border, so a structure reads as a hollow
    # shape.  We find each connected cluster of Outline blocks and fill its whole
    # bounding rectangle with dark non-solid textured blocks (one layer behind),
    # so the structure looks solid, then the outline sits on top.
    cells = set()
    for o in objs:
        if not re.match(r"^1,-?\d+", o):
            continue
        pk = H.parse_obj(o)
        if int(pk["id"]) in OUTLINE:
            cells.add((int(round((float(pk["x"]) - 15) / 30.0)),
                       int(round((float(pk["y"]) - 15) / 30.0))))
    seen = set()
    comps = []
    for c in cells:
        if c in seen:
            continue
        comp = []; q = deque([c]); seen.add(c)
        while q:
            x, y = q.popleft(); comp.append((x, y))
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    n = (x + dx, y + dy)
                    if n in cells and n not in seen:
                        seen.add(n); q.append(n)
        comps.append(comp)

    nfill = 0; nglow = 0; nlip = 0; ndet = 0
    for comp in comps:
        xs = [c[0] for c in comp]; ys = [c[1] for c in comp]
        xmin, xmax = min(xs), max(xs); ymin, ymax = min(ys), max(ys)
        w = xmax - xmin; h = ymax - ymin
        for cx in range(xmin, xmax + 1):
            for cy in range(ymin, ymax + 1):
                x = 15 + 30 * cx; y = 15 + 30 * cy
                edge = (cx == xmin or cx == xmax or cy == ymin or cy == ymax)
                chan = CH_INNER2 if edge else CH_INNER
                emit(SQ, x, y, CH_INNER, -1, 0, 0.0, 1.0, 1.0)   # dark base
                emit(TEX, x, y, chan, -1, 1, 0.0, 1.0, 1.0)      # texture
                nfill += 2
                if edge:  # rim glow, subtle
                    emit(SQ, x, y, CH_FIREGLW, -2, 1, random.uniform(0, 6.0), 0.85, 0.85)
                    nglow += 1
                if cy == ymin:  # bottom lip
                    emit(SQ, x, y, CH_HOT, -2, 2, random.uniform(0, 6.0), 0.6 + random.random()*0.2, 0.4)
                    nlip += 1
                if (cx - xmin) % 2 == 1 and 0 < cy < h:   # interior rivets
                    emit(SQ, x, y, CH_DETAIL, -1, 3, 0.0, 0.13, 0.13)
                    ndet += 1
            # top-trim rivet line: a small dark stud above each top cell
            emit(SQ, x, ymin * 30 + 15 + 12, CH_DETAIL, -1, 3, 0.0, 0.13, 0.13)
            ndet += 1
        # bright pulsing trim along the top edge (flashes on the beat)
        for cx in range(xmin, xmax + 1):
            emit(SQ, 15 + 30 * cx, 15 + 30 * ymax, CH_PULSE, -2, 3, 0.0, 0.86, 0.14)
            ndet += 1
        # vertical metal ribs every other interior column
        if w >= 2:
            for cx in range(xmin + 1, xmax, 2):
                ymid = 15 + 15 * (ymin + ymax)
                emit(SQ, 15 + 30 * cx, ymid, CH_PIPE, -1, 4, 0.0, 0.13, (h + 1) * 1.0)
                ndet += 1
        # cool complementary "cold light" node on multi-cell structures
        if (w >= 1 or h >= 2):
            emit(SQ, 15 + 30 * ((xmin + xmax) // 2), 15 + 30 * ymin, CH_PULSE_C, -2, 4, 0.0, 0.42, 0.42)
            ndet += 1
    print("structure clusters:", len(comps), " fill blocks:", nfill,
          " rim glow:", nglow, " lip:", nlip, " details:", ndet)

    # ---------------- recolour the existing structure ----------------
    # only the solid Outline blocks get the fire gradient; gameplay objects and
    # everything else are left exactly as they were.
    yspan = max(1.0, maxy - miny)
    out = []
    for o in objs:
        if not re.match(r"^1,-?\d+", o):
            out.append(o); continue
        pk = H.parse_obj(o)
        if int(pk["id"]) not in OUTLINE:
            out.append(o); continue
        try:
            yy = float(pk["y"])
            t = 1.0 - (yy - miny) / yspan     # 0 bottom(hot) -> 1 top(deep red)
            gi = int(round(max(0.0, min(1.0, t)) * (N_GRAD - 1)))
            out.append(set_obj_color(o, CH_GRAD0 + gi))
        except Exception:
            out.append(o)
    # ---------------- beat-synced pulses (music = Infernoplex, 175 BPM) --------
    def trig(tid, x, y, kv):
        d = [("1", tid), ("2", H.fnum(x)), ("3", H.fnum(y)), ("121", 1)]
        for k, v in kv:
            d.append((k, H.fnum(v) if isinstance(v, (int, float)) else v))
        added.append(",".join("%s,%s" % (k, v) for k, v in d))

    x_of = H.build_time_map(parsed or [])
    beat = 60.0 / BPM
    t = 0.0; k = 0; npulse = 0
    while x_of(t) <= maxx:
        px = x_of(t)
        if k % 4 == 0:
            # downbeat: white-hot flash (warm) + complementary cool accent
            trig(1006, px, 15, [("7", 255), ("8", 238), ("9", 200),
                                ("45", 0.04), ("46", 0.05), ("47", 0.18),
                                ("51", CH_PULSE), ("52", 0)])
            trig(1006, px, 15, [("7", COOL_RGB[0]), ("8", COOL_RGB[1]), ("9", COOL_RGB[2]),
                                ("45", 0.04), ("46", 0.05), ("47", 0.22),
                                ("51", CH_PULSE_C), ("52", 0)])
            trig(1006, px, 15, [("7", 255), ("8", 120), ("9", 20),
                                ("45", 0.05), ("46", 0.05), ("47", 0.30),
                                ("51", CH_FIREGLW), ("52", 0)])   # bg "thump"
            npulse += 3
        else:
            trig(1006, px, 15, [("7", 255), ("8", 120), ("9", 20),
                                ("45", 0.05), ("46", 0.05), ("47", 0.20),
                                ("51", CH_PULSE), ("52", 0)])
            npulse += 1
        t += beat; k += 1
    print("beat pulses:", npulse, " over", k, "beats")
    return out, added


def main():
    try:
        txt = read_level_container(SRC)
        old_k4 = H.get_k4(txt)
        header, objs = H.split_level(H.decode_level(old_k4))
    except Exception as e:
        # fallback to gmd
        txt = H.read_container(r"C:\Users\Tsunami74\Downloads\AxlAxolotl Collab.gmd")
        old_k4 = H.get_k4(txt)
        header, objs = H.split_level(H.decode_level(old_k4))
    parsed = [H.parse_obj(o) for o in objs if re.match(r"^1,-?\d+", o)]
    minx = min(p["x"] for p in parsed); maxx = max(p["x"] for p in parsed)
    miny = min(p["y"] for p in parsed); maxy = max(p["y"] for p in parsed)
    print("original objects:", len(objs), " x %.0f..%.0f y %.0f..%.0f"
          % (minx, maxx, miny, maxy))

    header = H.set_channels(header, REPAINT)

    tpl = [c for c in H.parse_channels(header) if c[0] == "1004"]
    tpl = tpl[0][2] if tpl else ("1_255_2_255_3_255_11_255_12_255_13_255_4_-1_"
                                 "6_1004_7_1_15_1_18_0_8_1")
    chans = [(CH_BG, BG_RGB, 0, 1.0, 1)]
    chans += [(CH_BAND0 + i, BAND_RGB[i], 0, 1.0, 1) for i in range(N_BAND)]
    chans += [(CH_DEEPRED, (120, 16, 10), 1, 0.5, 1),
              (CH_FIREGLW, (255, 110, 20), 1, 0.45, 1),
              (CH_EMBER, (255, 180, 70), 1, 0.8, 1),
              (CH_HOT, (255, 230, 150), 1, 0.6, 1)]
    chans += [(CH_GRAD0 + i, GRAD_RGB[i], 0, 1.0, 1) for i in range(N_GRAD)]
    chans += [(CH_INNER, INNER_RGB, 0, 1.0, 1),
              (CH_INNER2, INNER2_RGB, 0, 1.0, 1),
              (CH_EDGE, EDGE_RGB, 0, 1.0, 1)]
    chans += [(CH_DETAIL, RIVET_RGB, 0, 1.0, 1),
              (CH_PIPE, PIPE_RGB, 0, 1.0, 1),
              (CH_PULSE, PULSE_RGB, 1, 1.0, 1),      # blend on -> blooms when pulsed
              (CH_PULSE_C, PULSEC_RGB, 1, 1.0, 1)]
    header = H.add_channels(header, chans, tpl)

    new_objs, added = generate(objs, minx, maxx, miny, maxy, parsed)
    print("added deco objects:", len(added))

    new_level = header + ";" + ";".join(new_objs + added) + ";"
    new_k4 = H.encode_level(new_level)
    out = txt.replace("<k>k4</k><s>" + old_k4 + "</s>", "<k>k4</k><s>" + new_k4 + "</s>")
    out = re.sub(r"<k>k48</k><[si]>\d+</[si]>", "<k>k48</k><i>%d</i>" % (len(new_objs) + len(added)), out)
    write_level_container(DST, out)

    chk = read_level_container(DST)
    h2, o2 = H.split_level(H.decode_level(H.get_k4(chk)))
    print("VERIFY new objects:", len(o2), " (originals kept:", len(o2) >= len(objs), ")")
    try:
        print("wrote", DST, os.path.getsize(DST), "bytes")
    except Exception:
        pass


if __name__ == "__main__":
    main()
