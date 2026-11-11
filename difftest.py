import time
import numpy as np
from PIL import ImageGrab
import ctypes
from ctypes import wintypes

u32 = ctypes.windll.user32
k32 = ctypes.windll.kernel32

def find():
    h = u32.FindWindowW(None, "Geometry Dash")
    if not h:
        raise SystemExit("no GD window")
    return h

def focus(h):
    u32.ShowWindow(h, 9)
    time.sleep(0.2)
    fg = u32.GetForegroundWindow()
    u32.AttachThreadInput(k32.GetCurrentThreadId(), u32.GetWindowThreadProcessId(fg, None), True)
    u32.SetForegroundWindow(h); u32.BringWindowToTop(h)
    u32.AttachThreadInput(k32.GetCurrentThreadId(), u32.GetWindowThreadProcessId(fg, None), False)
    time.sleep(0.3)

def grab(h):
    r = wintypes.RECT(); u32.GetWindowRect(h, ctypes.byref(r))
    return np.asarray(ImageGrab.grab(bbox=(r.left, r.top, r.right, r.bottom)).convert("RGB"))

h = find(); focus(h)
print("fg window now:", hex(u32.GetForegroundWindow()), "target:", hex(h))
a = grab(h); time.sleep(0.6); b = grab(h)
d = np.abs(a.astype(int) - b.astype(int)).sum(axis=2)
changed = d > 30
print(f"frames {a.shape}, total changed px: {100*changed.mean():.2f}%")
ys, xs = np.where(changed)
if len(xs):
    print(f"changed bbox: x[{xs.min()},{xs.max()}] y[{ys.min()},{ys.max()}]")
# coarse 6x8 grid of change percentage
gh, gw = 6, 8
H, W = changed.shape
for gy in range(gh):
    row = []
    for gx in range(gw):
        blk = changed[gy*H//gh:(gy+1)*H//gh, gx*W//gw:(gx+1)*W//gw]
        row.append(f"{100*blk.mean():4.0f}")
    print("  " + " ".join(row))
