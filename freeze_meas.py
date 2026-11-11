import time
import numpy as np
import gd_run as g
from bg_cap import grab_print
import phase_driver
H = g.find_gl(); RECT = g.win_rect(H)
phase_driver.RECT = RECT
read = phase_driver.read
g.gentle_top(H); time.sleep(0.15); g.tap(0x20); time.sleep(0.4)

t0 = time.time(); last_t = None; streak = 0; frozen = None; rows = []; last_poll = 0.0
while time.time() - t0 < 60:
    frm, _ = grab_print(H)
    t, x = read(frm)
    now = time.time()
    if t != last_t:
        if t is not None and last_t is not None and t < last_t - 0.3 and frozen is not None:
            rows.append((round(now - frozen, 2), round(peakx, 0)))
            print(f"  death: freeze={now-frozen:.2f}s peak_x={peakx:.0f}", flush=True)
            frozen = None
        streak = 0
    else:
        streak += 1
        if frozen is None and t is not None and streak >= 3:
            frozen = now; peakx = x if x is not None else 0
    last_t = t
    time.sleep(0.03)
print("durations:", rows, flush=True)