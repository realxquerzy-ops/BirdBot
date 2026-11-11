import time
from PIL import Image
import gd_run as g

H = g.find_gl(); g.top(H); time.sleep(0.3)
Image.fromarray(g.grab()).save("now.png")
g.top(H); time.sleep(0.2)
Image.fromarray(g.grab()).save("now2.png")
print("ok")
