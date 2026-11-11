import time
import numpy as np
from PIL import ImageGrab
import ctypes
from ctypes import wintypes

u32 = ctypes.windll.user32
k32 = ctypes.windll.kernel32

HWND_TOP = 0
SWP_SHOWWINDOW = 0x40
SWP_FRAMECHANGED = 0x20

def find():
    h = u32.FindWindowW(None, "Geometry Dash")
    if not h:
        raise SystemExit("no GD window found")
    return h

def force_fullscreen(h):
    u32.ShowWindow(h, 9)          # restore
    time.sleep(0.15)
    u32.ShowWindow(h, 3)          # maximize
    time.sleep(0.15)
    # strip borders and cover primary monitor
    u32.SetWindowPos(h, HWND_TOP, 0, 0, 1920, 1080, SWP_SHOWWINDOW | SWP_FRAMECHANGED)
    time.sleep(0.15)
    fg = u32.GetForegroundWindow()
    u32.AttachThreadInput(k32.GetCurrentThreadId(), u32.GetWindowThreadProcessId(fg, None), True)
    u32.SetForegroundWindow(h)
    u32.BringWindowToTop(h)
    u32.AttachThreadInput(k32.GetCurrentThreadId(), u32.GetWindowThreadProcessId(fg, None), False)
    time.sleep(0.4)

def rect(h):
    r = wintypes.RECT(); u32.GetWindowRect(h, ctypes.byref(r))
    return (r.left, r.top, r.right, r.bottom)

h = find()
force_fullscreen(h)
print("target fg == actual fg:", u32.GetForegroundWindow() == h)

frames = []
for i in range(4):
    box = rect(h)
    img = ImageGrab.grab(bbox=box, all_screens=True).convert("RGB")
    a = np.asarray(img)
    frames.append(a)
    u32.SetWindowPos(h, HWND_TOP, 0, 0, 1920, 1080, SWP_SHOWWINDOW)
    print(f"frame {i}: rect={box} size={a.shape[1]}x{a.shape[0]} mean={a.mean():.1f}")
    time.sleep(0.35)

if all(f.shape == frames[0].shape for f in frames):
    for i in range(len(frames) - 1):
        d = np.abs(frames[i].astype(int) - frames[i+1].astype(int)).sum(2)
        ch = d > 30
        ys, xs = np.where(ch)
        bb = f"x[{xs.min()},{xs.max()}] y[{ys.min()},{ys.max()}]" if len(xs) else "none"
        print(f"motion {i}->{i+1}: {100*ch.mean():.2f}% changed  bbox {bb}")

Image.fromarray(frames[0]).save("full0.png")
Image.fromarray(frames[-1]).save("full_last.png")
print("saved full0.png full_last.png")
