import ctypes, time
from ctypes import wintypes
import numpy as np
from PIL import ImageGrab, Image

u32 = ctypes.windll.user32
g32 = ctypes.windll.gdi32
HWND_TOPMOST = -1
SWP_SHOWWINDOW = 0x40
SWP_FRAMECHANGED = 0x20
SWP_NOSIZE = 0x1
SWP_NOMOVE = 0x2

def find_gl_window():
    res = []
    PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(h, l):
        b = ctypes.create_unicode_buffer(256); u32.GetClassNameW(h, b, 256)
        if b.value == "GLFW30":
            n = u32.GetWindowTextLengthW(h); t = ctypes.create_unicode_buffer(n+1)
            u32.GetWindowTextW(h, t, n+1)
            if t.value == "Geometry Dash":
                res.append(h)
        return True
    u32.EnumWindows(PROC(cb), 0)
    return res[0] if res else None

h = find_gl_window()
print("render window:", h)
u32.ShowWindow(h, 9)                       # restore
time.sleep(0.2)
u32.SetWindowPos(h, HWND_TOPMOST, 0, 0, 1920, 1080, SWP_SHOWWINDOW | SWP_FRAMECHANGED)
time.sleep(0.5)

def rect(h):
    r = wintypes.RECT(); u32.GetWindowRect(h, ctypes.byref(r)); return (r.left, r.top, r.right, r.bottom)

frames = []
for i in range(5):
    u32.SetWindowPos(h, HWND_TOPMOST, 0, 0, 1920, 1080, SWP_SHOWWINDOW)
    box = rect(h)
    a = np.asarray(ImageGrab.grab(bbox=box, all_screens=True).convert("RGB"))
    frames.append(a)
    print(f"frame {i}: rect={box} mean={a.mean():.1f}")
    time.sleep(0.3)

for i in range(len(frames)-1):
    a, b = frames[i], frames[i+1]
    if a.shape == b.shape:
        d = np.abs(a.astype(np.int16)-b.astype(np.int16)).sum(2); ch = d > 30
        ys, xs = np.where(ch)
        bb = (int(xs.min()),int(ys.min()),int(xs.max()),int(ys.max())) if len(xs) else None
        print(f"motion {i}->{i+1}: {100*ch.mean():.2f}%  bbox={bb}")

Image.fromarray(frames[0]).save("game_a.png")
Image.fromarray(frames[-1]).save("game_b.png")
print("saved game_a.png game_b.png")
