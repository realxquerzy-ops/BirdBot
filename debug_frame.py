import time
from ctypes import wintypes
import numpy as np
from PIL import Image
import gd_run as g

H = g.find_gl()
g.top(H); time.sleep(0.4)
Image.fromarray(g.grab()).save("dbg1.png")
print("dbg1:", {k: v for k, v in g.read_state(g.grab()).items() if k != 'raw'})

g.tap(g.VK_R); time.sleep(0.5); g.top(H)
Image.fromarray(g.grab()).save("dbg2.png")
print("dbg2:", {k: v for k, v in g.read_state(g.grab()).items() if k != 'raw'})

for _ in range(25):
    g.tap(g.VK_SPACE); time.sleep(0.04)
time.sleep(0.3); g.top(H)
frame = g.grab(); Image.fromarray(frame).save("dbg3.png")
st = g.read_state(frame)
print("dbg3:", {k: v for k, v in st.items() if k != 'raw'})
print("raw3:", st['raw'][:200])
