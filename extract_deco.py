"""
extract_deco.py - transplant REAL deco motifs from a modern reference level
("Kumomi") onto the Hypei gameplay route, instead of procedurally inventing
block designs.

How it works:
  1. Load the reference, cluster its deco objects into spatial "motifs".
  2. Keep block-sized motifs (a real block design: base+face+3D+detail) and
     feature-sized motifs (larger focal clusters).
  3. For every gameplay block on the Hypei route, stamp a block motif at the
     block centre; occasionally stamp a feature motif between blocks.
  4. Colours are mapped reference-RGB -> nearest warm palette channel, so the
     modern palette is preserved.

Run:  python extract_deco.py   (writes Hypei.gmd)
"""
import re, gzip, base64, math, random, json, os, sys
import render_gmd as R

SRC = r"C:\Users\Tsunami74\Downloads\Hypei Layout.gmd"
REF = r"C:\Users\Tsunami74\Downloads\Kumomi.gmd"
DST = r"C:\Users\Tsunami74\Downloads\Hypei.gmd"

# gameplay / structural ids we decorate (solid blocks + spikes)
BLOCK_IDS = {1, 2, 3, 4}
SPIKE_IDS = {8, 39, 103}
SKIP = R.TRIGGER_IDS | R.TEXT_IDS | BLOCK_IDS | SPIKE_IDS

# warm palette (must match hypei_deco WARM)
WARM = [
    (1020, (26, 25, 25)), (1021, (48, 43, 39)), (1022, (255, 229, 82)),
    (1023, (255, 235, 121)), (1024, (198, 197, 185)), (1025, (244, 151, 142)),
    (1026, (87, 108, 168)), (1027, (254, 205, 170)), (1028, (253, 255, 187)),
    (1029, (255, 255, 255)), (1030, (39, 70, 144)),
]


def nearest_channel(rgb):
    r, g, b = rgb
    best, bestd = WARM[0][0], 1e18
    for cid, (cr, cg, cb) in WARM:
        d = (cr - r) ** 2 + (cg - g) ** 2 + (cb - b) ** 2
        if d < bestd:
            bestd, best = d, cid
    return best


def fnum(v):
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    if isinstance(v, int):
        return str(v)
    return ("%.3f" % float(v)).rstrip("0").rstrip(".")


def g30(v):
    return 15 + 30 * int(round((v - 15) / 30.0))


# ---------------------------------------------------------------- motif mining
def mine_motifs(ref, span_small=(18, 52), span_large=(52, 150)):
    """cluster reference deco into motifs; return (block_motifs, feature_motifs)."""
    deco = []
    for o in ref.parsed:
        if o["id"] in SKIP:
            continue
        (r, g, b), op = R.resolve_color(o, ref.channels)
        if op <= 0.05:
            continue
        sx = float(o.get("128", 1) or 1)
        sy = float(o.get("129", 1) or 1)
        rot = float(o.get("6", 0) or 0)
        # preserve "uncolored" objects (no key 21) -> they inherit the level Obj colour
        chan = nearest_channel((r, g, b)) if "21" in o else None
        deco.append({"id": o["id"], "x": o["x"], "y": o["y"],
                     "sx": sx, "sy": sy, "rot": rot, "rgb": (r, g, b), "chan": chan})

    # bucket by 40u grid, gather neighbours within 70u
    CELL = 40.0
    buckets = {}
    for d in deco:
        key = (int(d["x"] // CELL), int(d["y"] // CELL))
        buckets.setdefault(key, []).append(d)

    seen = set()
    block_motifs, feature_motifs = [], []
    for key, group in buckets.items():
        # expand: pull all deco within 70u of bucket centroid
        cx = sum(d["x"] for d in group) / len(group)
        cy = sum(d["y"] for d in group) / len(group)
        members = [d for d in deco
                   if (d["x"] - cx) ** 2 + (d["y"] - cy) ** 2 < 70 * 70]
        if len(members) < 3:
            continue
        # signature for dedupe: sorted id multiset + rounded span
        xs = [d["x"] for d in members]; ys = [d["y"] for d in members]
        spanx = max(xs) - min(xs); spany = max(ys) - min(ys)
        span = max(spanx, spany)
        sig = (tuple(sorted(d["id"] for d in members)), int(span // 10))
        if sig in seen:
            continue
        seen.add(sig)
        mx = sum(d["x"] for d in members) / len(members)
        my = sum(d["y"] for d in members) / len(members)
        motif = {
            "span": span,
            "members": [{"id": d["id"], "dx": d["x"] - mx, "dy": d["y"] - my,
                         "sx": d["sx"], "sy": d["sy"], "rot": d["rot"],
                         "chan": d["chan"]} for d in members],
        }
        if span_small[0] <= span <= span_small[1] and 3 <= len(members) <= 14:
            block_motifs.append(motif)
        elif span_large[0] <= span <= span_large[1] and 4 <= len(members) <= 22:
            feature_motifs.append(motif)
    return block_motifs, feature_motifs


# ---------------------------------------------------------------- apply to route
def build_time_map(objs):
    PORTAL = {200: 251.16, 201: 311.58, 202: 387.42, 203: 468.0}
    portals = sorted(((o["x"], o["id"]) for o in objs if o["id"] in PORTAL), key=lambda t: t[0])
    maxx = max(o["x"] for o in objs) + 2000
    cur = PORTAL[201]; prev = 0.0; segs = []
    for x, pid in portals:
        if x <= 30:
            cur = PORTAL[pid]; continue
        segs.append((prev, cur)); cur = PORTAL[pid]; prev = x
    segs.append((prev, cur))
    times = [0.0]
    for i in range(1, len(segs)):
        times.append(times[-1] + (segs[i][0] - segs[i - 1][0]) / segs[i - 1][1])
    def x_of(t):
        if t <= 0: return 0.0
        for i in range(len(segs)):
            t0 = times[i]; x0, sp = segs[i]
            x1 = segs[i + 1][0] if i + 1 < len(segs) else maxx + 1e6
            t1 = t0 + (x1 - x0) / sp
            if t <= t1: return x0 + (t - t0) * sp
        return 0.0
    return x_of


def generate(objs, block_motifs, feature_motifs):
    rng = random.Random(11)
    added = []
    def emit(id_, x, y, chan, zl, zo, rot=0.0, sx=1.0, sy=1.0):
        d = [("1", id_), ("2", fnum(x)), ("3", fnum(y))]
        if chan is not None:
            d.append(("21", chan))
        d += [("25", zo), ("128", fnum(sx)), ("129", fnum(sy))]
        if rot: d.append(("6", fnum(rot)))
        if zl is not None: d.append(("24", zl))
        d.append(("121", 1))
        added.append(",".join("%s,%s" % (k, v) for k, v in d))

    # 0. modern background : big soft circles + shapes behind everything
    CIRC, TCIRC, SPLIT, HOLLOW, CLOUD_M, GEAR = 3637, 1764, 998, 3622, 223, 1735
    BG_TONES = [1021, 1026, 1027, 1024]   # brown, blue-gray, peach, cream
    xs0 = [o["x"] for o in objs]
    rb_x = [o["x"] for o in objs]
    startx, endx = min(xs0), max(xs0)
    bx = 15 + 30 * int(math.floor((startx - 15) / 30.0))
    rng = random.Random(23)
    while bx < endx:
        cy = rng.choice([180.0, 380.0, 620.0, 840.0])
        emit(rng.choice([CIRC, CIRC, SPLIT]), bx, cy, rng.choice(BG_TONES),
             1, -330, 0, rng.uniform(1.8, 3.4), rng.uniform(1.8, 3.4))
        bx += rng.choice([540, 720, 900])
    # tiny circle speckle field
    bx = 15 + 30 * int(math.floor((startx - 15) / 30.0))
    while bx < endx:
        emit(TCIRC, bx, rng.uniform(70, 900), 1021, 3, -310, 0, 0.5, 0.5)
        bx += rng.choice([210, 330])
    # soft cloud / gear accents scattered in the sky
    bx = 15 + 30 * int(math.floor((startx - 15) / 30.0))
    while bx < endx:
        emit(rng.choice([CLOUD_M, GEAR]), bx, rng.choice([260.0, 560.0, 800.0]),
             rng.choice([1027, 1024, 1026]), 5, -150, rng.uniform(0, 360),
             rng.uniform(0.8, 1.6), rng.uniform(0.8, 1.6))
        bx += rng.choice([420, 600, 840])

    # 1. stamp a real block-design motif on every 2nd gameplay block (breathe)
    if block_motifs:
        j = 0
        bi = 0
        for o in objs:
            if o["id"] not in BLOCK_IDS:
                continue
            if bi % 2 == 0:
                m = block_motifs[j % len(block_motifs)]
                j += 1
                for mem in m["members"]:
                    emit(mem["id"], g30(o["x"] + mem["dx"]), g30(o["y"] + mem["dy"]),
                         mem["chan"], 3, 5, mem["rot"], mem["sx"] * 0.85, mem["sy"] * 0.85)
            bi += 1

    # 2. occasional feature motif between blocks (focal decoration)
    if feature_motifs:
        blocks = [o for o in objs if o["id"] in BLOCK_IDS]
        for i, o in enumerate(blocks):
            if i % 12 == 0:
                m = feature_motifs[(i // 12) % len(feature_motifs)]
                for mem in m["members"]:
                    emit(mem["id"], g30(o["x"] + 40 + mem["dx"]), g30(o["y"] + 30 + mem["dy"]),
                         mem["chan"], 5, 26, mem["rot"], mem["sx"] * 0.8, mem["sy"] * 0.8)

    # 3. ground edge + beat pulses (kept from modern pass, warm)
    xs = [o["x"] for o in objs]
    minx, maxx = min(xs), max(xs)
    x = 15 + 30 * int(math.floor((minx - 15) / 30.0))
    while x < maxx:
        emit(211, x, 15, 1030, 1, -20, 0, 4, 1)      # deep-blue floor base
        emit(211, x, 30, 1021, 3, -18, 0, 4, 0.08)   # dim brown top edge
        x += 120
    x_of = build_time_map(objs)
    beat = 60.0 / 176.0; t = 0.0; k = 0
    while x_of(t) <= maxx:
        px = x_of(t)
        rgb = (255, 210, 150) if k % 2 == 0 else (130, 165, 255)
        added.append(",".join("%s,%s" % (kv) for kv in [
            ("1", 1006), ("2", fnum(px)), ("3", "465"), ("21", "101"), ("25", "0"),
            ("36", "1"), ("52", "1"), ("51", "101"), ("45", "0.2"), ("46", "0.3"),
            ("47", "0.4"), ("210", "1"), ("7", rgb[0]), ("8", rgb[1]), ("9", rgb[2])]))
        t += beat; k += 1
    return added


def main():
    ref = R.Level(REF)
    print("reference objects:", len(ref.parsed))
    bm, fm = mine_motifs(ref)
    print("block motifs:", len(bm), " feature motifs:", len(fm))
    if bm:
        print("  sample block motif: span=%.0f members=%d ids=%s" %
              (bm[0]["span"], len(bm[0]["members"]), [m["id"] for m in bm[0]["members"]][:8]))

    txt = R.read_container(SRC)
    old_k4 = R.get_k4(txt)
    header, objs = R.split_level(R.decode_level(old_k4))
    parsed = [R.parse_obj(o) for o in objs if re.match(r"^1,-?\d+", o)]
    print("layout objects:", len(parsed))

    # warm palette channels (same as hypei_deco)
    header = R.set_channels(header, {
        "1000": (255, 176, 133), "1001": (0, 102, 255), "1009": (0, 102, 255),
        "1002": (255, 255, 255), "1004": (255, 255, 255), "1003": (72, 62, 55),
        "1013": (40, 125, 255), "1014": (40, 125, 255),
    })
    tpl = [c for c in R.parse_channels(header) if c[0] == "1004"]
    tpl = tpl[0][2] if tpl else "1_255_2_255_3_255_11_255_12_255_13_255_4_-1_6_1004_7_1_15_1_18_0_8_1"
    # re-add channels with full fields so opacity/blend survive
    def channel_str(cid, r, g, b, template):
        d, f = R._chan_dict(template)
        d["1"], d["2"], d["3"], d["6"] = str(r), str(g), str(b), str(cid)
        d["18"] = "0"; d["7"] = "1"
        return "_".join("%s_%s" % (k, d[k]) for k in f[::2])
    extra = "".join("|" + channel_str(c, r, g, b, tpl) for c, (r, g, b) in WARM)
    m = re.search(r"(kS38,)(.*?)(,kA13|,kS39|$)", header)
    ks38 = m.group(2)
    if not ks38.endswith("|"): ks38 += "|"
    ks38 += extra.lstrip("|")
    header = header[:m.start(2)] + ks38 + header[m.end(2):]

    added = generate(parsed, bm, fm)
    print("added deco objects:", len(added))

    new_level = header + ";" + ";".join(objs + added) + ";"
    new_k4 = R.encode_level(new_level)
    out = txt.replace("<k>k4</k><s>" + old_k4 + "</s>", "<k>k4</k><s>" + new_k4 + "</s>")
    out = out.replace("<k>k2</k><s>Hypei Layout</s>", "<k>k2</k><s>Hypei</s>")
    out = re.sub(r"<k>k48</k><i>\d+</i>", "<k>k48</k><i>%d</i>" % (len(objs) + len(added)), out)
    open(DST, "wb").write(out.encode("utf-8"))
    print("wrote", DST, os.path.getsize(DST), "bytes")

    # verify via renderer
    L = R.Level(DST)
    print("VERIFY objects:", len(L.parsed), " metrics:", R.metrics(L, route=True))


if __name__ == "__main__":
    main()
