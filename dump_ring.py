import time, glob, os
import numpy as np
from PIL import Image
import gd_run as g
from bg_cap import grab_print
from phase_driver import read
import phase_driver

H = g.find_gl(); RECT = g.win_rect(H); phase_driver.RECT = RECT
for f in glob.glob("dump_*.png"): os.remove(f)

g.gentle_top(H); time.sleep(0.15); g.tap(0x20); time.sleep(0.4)
ring = []; last_t = None; started = False; saved = False; t0 = time.time()

while time.time() - t0 < 60 and not saved:
    frm, _ = grab_print(H)
    ring.append(frm.copy())
    if len(ring) > 40: ring.pop(0)
    t, x = read(frm)
    if t is not None:
        if not started and t < 1.0:
            g.tap(0x20, hold=1.4); started = True; print("hold started", flush=True)
        elif started and last_t is not None and t < last_t - 0.3:
            # death detected -> dump ring
            for i, fr in enumerate(ring):
                Image.fromarray(fr).save(f"dump_{i:02d}.png")
            saved = True
            print("death -> dumped", flush=True)
        last_t = t
    time.sleep(0.015)
print("frames:", len(ring), flush=True)