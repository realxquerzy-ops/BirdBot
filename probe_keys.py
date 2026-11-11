import time
import gd_core as g

h = g.find_window()
g.force_fullscreen(h)
time.sleep(0.5)

KEYS = {"space": 0x20, "enter": 0x0D, "esc": 0x1B, "p": 0x50, "r": 0x52,
        "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27, "tab": 0x09}

print("probing keys (each: tap, wait, measure motion)...")
for name, vk in KEYS.items():
    g.keep_on_top(h)
    a = g.grab(h)
    g.tap(vk)
    time.sleep(0.45)
    b = g.grab(h)
    pct, bb = g.changed_pct(a, b)
    print(f"  {name:6s} vk=0x{vk:02x}  changed={pct:6.2f}%  bbox={bb}")
    time.sleep(0.25)
