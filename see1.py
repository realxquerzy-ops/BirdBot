import time
from PIL import Image
import gd_run as g

H = g.find_gl(); g.top(H); time.sleep(0.2)
g.tap(0x20); time.sleep(0.2)
for i in range(5):
    g.top(H)
    Image.fromarray(g.grab()).save(f"see{i}.png")
    time.sleep(0.8)
print("ok")