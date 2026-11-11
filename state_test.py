import time
import gd_core as g

h = g.find_window()
print("fg_before ==", g.focused(h))
g.force_fullscreen(h)
time.sleep(0.4)
print("focused now:", g.focused(h), "rect:", g.window_rect(h))

a = g.grab(h)
time.sleep(0.40)
b = g.grab(h)
pct, bb = g.changed_pct(a, b)
print(f"[state check] changed={pct:.2f}%  bbox={bb}  -> {'PAUSED' if g.is_static(a,b) else 'PLAYING'}")

if g.is_static(a, b):
    print("pressing SPACE to unpause...")
    g.tap()
    time.sleep(0.5)
    c = g.grab(h)
    time.sleep(0.40)
    d = g.grab(h)
    pct2, bb2 = g.changed_pct(c, d)
    print(f"[after space] changed={pct2:.2f}%  bbox={bb2}  -> {'PAUSED' if g.is_static(c,d) else 'PLAYING'}")
    from PIL import Image
    Image.fromarray(c).save("state_c.png")
    Image.fromarray(d).save("state_d.png")

from PIL import Image
Image.fromarray(a).save("state_a.png")
Image.fromarray(b).save("state_b.png")
print("saved state_a/b/c/d.png")
