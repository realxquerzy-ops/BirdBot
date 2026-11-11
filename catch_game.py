import ctypes, time
from ctypes import wintypes
import numpy as np
from PIL import ImageGrab, Image

u32 = ctypes.windll.user32
k32 = ctypes.windll.kernel32
HWND_TOPMOST = -1
SWP_SHOWWINDOW = 0x40

def find_gl():
    res = []
    PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(h, l):
        b = ctypes.create_unicode_buffer(256); u32.GetClassNameW(h, b, 256)
        if b.value == "GLFW30":
            n = u32.GetWindowTextLengthW(h); t = ctypes.create_unicode_buffer(n+1)
            u32.GetWindowTextW(h, t, n+1)
            if t.value == "Geometry Dash": res.append(h)
        return True
    u32.EnumWindows(PROC(cb), 0)
    return res[0] if res else None

def rect(h):
    r = wintypes.RECT(); u32.GetWindowRect(h, ctypes.byref(r)); return (r.left,r.top,r.right,r.bottom)

def focus(h):
    fg = u32.GetForegroundWindow()
    u32.AttachThreadInput(k32.GetCurrentThreadId(), u32.GetWindowThreadProcessId(fg, None), True)
    u32.SetForegroundWindow(h); u32.BringWindowToTop(h)
    u32.AttachThreadInput(k32.GetCurrentThreadId(), u32.GetWindowThreadProcessId(fg, None), False)

h = find_gl()
print("gl window", h)
box = (0, 0, 1920, 1080)
ref = np.asarray(ImageGrab.grab(bbox=box, all_screens=True).convert("RGB"))
print("reference (desktop) captured")

got = None
for i in range(50):
    u32.ShowWindow(h, 9)                 # SW_RESTORE
    focus(h)
    u32.SetWindowPos(h, HWND_TOPMOST, 0, 0, 1920, 1080, SWP_SHOWWINDOW)
    a = np.asarray(ImageGrab.grab(bbox=box, all_screens=True).convert("RGB"))
    d = np.abs(a.astype(np.int16) - ref.astype(np.int16)).sum(2)
    pct = 100.0 * (d > 30).mean()
    fg = u32.GetForegroundWindow() == h
    print(f"iter {i}: rect={rect(h)} gamefocus={fg} diff_vs_desktop={pct:.1f}%")
    if pct > 5.0:
        Image.fromarray(a).save("game_live.png")
        print("  -> GAME VISIBLE, saved game_live.png")
        got = a
        break
    time.sleep(0.08)
if got is None:
    print("never caught the game frame")
