import ctypes, time, sys
from ctypes import wintypes
import numpy as np
from PIL import ImageGrab, Image

u32 = ctypes.windll.user32
k32 = ctypes.windll.kernel32
HWND_TOPMOST = -1
SWP_SHOWWINDOW = 0x40

KEYS = {"space": 0x20, "tab": 0x09, "r": 0x52, "esc": 0x1B, "enter": 0x0D,
        "shift": 0x10, "ctrl": 0x11, "up": 0x26, "down": 0x28}

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

def focus(h):
    fg = u32.GetForegroundWindow()
    u32.AttachThreadInput(k32.GetCurrentThreadId(), u32.GetWindowThreadProcessId(fg, None), True)
    u32.SetForegroundWindow(h); u32.BringWindowToTop(h)
    u32.AttachThreadInput(k32.GetCurrentThreadId(), u32.GetWindowThreadProcessId(fg, None), False)

def tap(vk):
    u32.keybd_event(vk, 0, 0, 0); time.sleep(0.02); u32.keybd_event(vk, 0, 2, 0)

h = find_gl()
key = sys.argv[1] if len(sys.argv) > 1 else "tab"
out = sys.argv[2] if len(sys.argv) > 2 else "tab.png"
u32.ShowWindow(h, 9); focus(h); u32.SetWindowPos(h, HWND_TOPMOST, 0, 0, 1920, 1080, SWP_SHOWWINDOW)
time.sleep(0.4)
tap(KEYS[key.lower()])
time.sleep(0.6)
u32.ShowWindow(h, 9); focus(h); u32.SetWindowPos(h, HWND_TOPMOST, 0, 0, 1920, 1080, SWP_SHOWWINDOW)
time.sleep(0.2)
a = np.asarray(ImageGrab.grab(bbox=(0,0,1920,1080), all_screens=True).convert("RGB"))
Image.fromarray(a).save(out)
print(f"pressed {key}, saved {out}")
