import time
from PIL import Image
import gd_run as g

H = g.find_gl(); g.top(H); time.sleep(0.15)
g.tap(g.VK_R); time.sleep(0.25); g.tap(g.VK_SPACE); time.sleep(0.4)
g.top(H)
Image.fromarray(g.grab()).save("warp.png")
print("ok")
