import time
import gd_run as g, ocr_mod
from learner2 import read_t_a

H = g.find_gl()
g.top(H); g.tap(g.VK_R); time.sleep(0.25)
last = None; tstart = time.time(); fired = False
while time.time() - tstart < 12.0:
    tv, av, s = read_t_a()
    el = time.time() - tstart
    if not fired and tv is not None:
        g.tap(0x20); fired = True
    print(f"el={el:5.2f}  Time={tv}  Att={av}  | {s[:60]}")
    time.sleep(0.05)
    if tv is not None and last is not None and tv < last - 0.2:
        print("  >Time reset<")
        break
    if tv is not None:
        last = tv
