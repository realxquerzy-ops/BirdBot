import time
from PIL import Image
import gd_run as g

H = g.find_gl()
print("rect before", end=" ")
import ctypes
from ctypes import wintypes
r = wintypes.RECT(); g.u32.GetWindowRect(H, ctypes.byref(r))
print(r.left, r.top, r.right, r.bottom)
g.u32.ShowWindow(H, 3)
g.top(H); time.sleep(0.6)
g.tap(g.VK_R); time.sleep(0.4); g.tap(g.VK_SPACE); time.sleep(0.5)
g.top(H); time.sleep(0.2)
Image.fromarray(g.grab()).save("restore.png")
r = wintypes.RECT(); g.u32.GetWindowRect(H, ctypes.byref(r))
print("rect after", r.left, r.top, r.right, r.bottom)
print("ok")
