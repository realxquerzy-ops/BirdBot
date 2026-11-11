import time, re, sys
import numpy as np
from PIL import Image
import gd_run as g, ocr_mod

H = None

def read_frame():
    g.top(H)
    img = Image.fromarray(g.grab()).crop((0, 0, 340, 300))
    img = img.resize((img.width*3, img.height*3), Image.LANCZOS)
    a = np.asarray(img.convert("L"))
    inv = 255 - np.where(a > max(110, int(np.percentile(a, 70))), 255, 0).astype(np.uint8)
    s = ocr_mod.ocr_img(Image.fromarray(inv))
    def g1(p):
        m = re.search(p, s); return float(m.group(1)) if m else None
    return g1(r"Time[:\s]*([0-9]+\.[0-9]+)"), g1(r"[xX][:\s]*([0-9]+)"), g1(r"Attempt[:\s]*([0-9]+)")

def drive(schedule, nattempts=8, cap=8.0):
    g.top(H); time.sleep(0.2); g.tap(0x20); time.sleep(0.4)
    def new_att():
        return {"fired": [False]*len(schedule), "maxt": 0.0, "maxx": 0.0,
                "lastt": None, "lastx": None, "ots": time.time()}
    cur = new_att(); windowatt = None
    results = []
    t0 = time.time()
    while time.time() - t0 < nattempts*(cap) + 5 and len(results) < nattempts:
        t, x, att = read_frame()
        if windowatt is None: windowatt = att
        if t is not None:
            if cur["lastt"] is not None and t < cur["lastt"] - 0.25:
                results.append((cur["maxt"], cur["maxx"], cur["lastt"], cur["lastx"], cur["ots"]))
                cur = new_att(); windowatt = att
                continue
            if t > cur["maxt"]: cur["maxt"] = t
            cur["lastt"] = t
        if x is not None:
            if x > cur["maxx"]: cur["maxx"] = x
            cur["lastx"] = x
        if att is not None and windowatt is not None and att > windowatt:
            results.append((cur["maxt"], cur["maxx"], cur["lastt"], cur["lastx"], cur["ots"]))
            cur = new_att(); windowatt = att
        for i, tg in enumerate(schedule):
            if not cur["fired"][i] and cur["lastt"] is not None and cur["lastt"] >= tg:
                g.tap(0x20); cur["fired"][i] = True
        time.sleep(0.03)
    results.append((cur["maxt"], cur["maxx"], cur["lastt"], cur["lastx"], cur["ots"]))
    return results

if __name__ == "__main__":
    H = g.find_gl()
    sched = [float(x) for x in sys.argv[1].split(",")] if len(sys.argv) > 1 else [0.4]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    res = drive(sched, n)
    for i, (mt, mx, dt, dx, ots) in enumerate(res):
        status = "ALIVE@cap" if dt is None else "death"
        print(f"att {i:2d}: maxT={mt:.2f} maxX={mx:.0f}  ({status} t={dt} x={dx})")