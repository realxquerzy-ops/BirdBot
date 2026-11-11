import time
import numpy as np
from PIL import Image
import gd_run as g

VK_TAB = 0x09
H = g.find_gl(); g.top(H); time.sleep(0.25)
g.tap(VK_TAB); time.sleep(0.5); g.top(H); time.sleep(0.2)
Image.fromarray(g.grab()).save("menu_open.png")
g.tap(VK_TAB); time.sleep(0.5); g.top(H); time.sleep(0.2)
Image.fromarray(g.grab()).save("menu_closed.png")
print("saved menu_open.png / menu_closed.png")
