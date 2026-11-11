import time, ctypes
from ctypes import wintypes
import gd_run as g

H = g.find_gl()
g.focus(H); time.sleep(0.25)
g.u32.keybd_event(0x12, 0, 0, 0)
g.u32.keybd_event(0x0D, 0, 0, 0)
time.sleep(0.06)
g.u32.keybd_event(0x0D, 0, 2, 0)
g.u32.keybd_event(0x12, 0, 2, 0)
time.sleep(0.9)
r = wintypes.RECT(); g.u32.GetWindowRect(H, ctypes.byref(r))
print("rect after Alt+Enter:", r.left, r.top, r.right, r.bottom)
g.top(H); time.sleep(0.3)
from PIL import Image
Image.fromarray(g.grab()).save("after_alt.png")
print("saved")
