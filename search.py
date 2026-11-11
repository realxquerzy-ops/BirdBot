import time, re, random, sys
import numpy as np
from PIL import Image
import gd_run as g, ocr_mod

H = None
random.seed(3)

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

def new_att(sched):
    return {"fired": [False]*len(sched), "maxx": 0.0, "lastt": None}

def eval_sched(sched, seconds=9.0, early_stop=2600.0):
    cur = new_att(sched); windowatt = None
    best = 0.0
    t0 = time.time()
    while time.time() - t0 < seconds:
        t, x, att = read_frame()
        if t is not None and cur["lastt"] is not None and t < cur["lastt"] - 0.25:
            cur = new_att(sched); windowatt = att
            continue
        if att is not None and windowatt is not None and att > windowatt:
            cur = new_att(sched); windowatt = att
        if att is not None:
            windowatt = att
        if x is not None and x > cur["maxx"]:
            cur["maxx"] = x
        if t is not None:
            cur["lastt"] = t
        for i, tg in enumerate(sched):
            if not cur["fired"][i] and cur["lastt"] is not None and cur["lastt"] >= tg:
                g.tap(0x20); cur["fired"][i] = True
        if cur["maxx"] > best:
            best = cur["maxx"]
        time.sleep(0.03)
    return best

def mutate(sched):
    s = list(sched)
    if random.random() < 0.62 or len(s) < 2:
        nt = round(random.uniform(0.15, min(6.5, (len(s)*0.85 + 0.3))), 2)
        s.append(nt)
    else:
        j = random.randrange(len(s))
        s[j] = round(min(6.5, max(0.15, s[j] + random.uniform(-0.18, 0.18))), 2)
    s = sorted(set(s))
    out = []
    for v in s:
        if not out or v - out[-1] >= 0.12:
            out.append(v)
    return out[:14]

if __name__ == "__main__":
    H = g.find_gl()
    best_sched = [0.45]
    best_evals = {tuple(best_sched): []}
    best_fit = 0.0
    g.top(H); time.sleep(0.2); g.tap(0x20); time.sleep(0.3)
    for it in range(int(sys.argv[1]) if len(sys.argv) > 1 else 16):
        cand = mutate(best_sched)
        fit = eval_sched(cand)
        improved = fit > best_fit
        if improved:
            best_fit = fit; best_sched = cand
        print(f"it {it:2d} sched={[round(s,2) for s in cand]} fit={fit:.0f}  {'<< NEW BEST' if improved else ''}")
        if best_fit >= 3000:
            print("REACHED 3000+ ; stopping early")
            break
    print("BEST:", [round(s,2) for s in best_sched], "fit", best_fit)