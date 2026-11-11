import ctypes, time
from ctypes import wintypes
import numpy as np
from PIL import ImageGrab, Image

u32 = ctypes.windll.user32
k32 = ctypes.windll.kernel32
HWND_TOPMOST = -1
SWP_SHOWWINDOW = 0x40
VK_SPACE = 0x20

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

u32.keybd_event(VK_SPACE, 0, 0, 0); u32.keybd_event(VK_SPACE, 0, 2, 0)

def focus(h):
    fg = u32.GetForegroundWindow()
    u32.AttachThreadInput(k32.GetCurrentThreadId(), u32.GetWindowThreadProcessId(fg, None), True)
    u32.SetForegroundWindow(h); u32.BringWindowToTop(h)
    u32.AttachThreadInput(k32.GetCurrentThreadId(), u32.GetWindowThreadProcessId(fg, None), False)

def grab():
    return np.asarray(ImageGrab.grab(bbox=(0,0,1920,1080), all_screens=True).convert("RGB"))

h = find_gl(); print("gl", h)
last = None
for i in range(6):
    u32.ShowWindow(h, 9); focus(h)
    u32.SetWindowPos(h, HWND_TOPMOST, 0, 0, 1920, 1080, SWP_SHOWWINDOW)
    a = grab()
    u32.keybd_event(VK_SPACE, 0, 0, 0); time.sleep(0.08); u32.keybd_event(VK_SPACE, 0, 2, 0)
    time.sleep(0.30)
    u32.ShowWindow(h, 9); focus(h); u32.SetWindowPos(h, HWND_TOPMOST, 0, 0, 1920, 1080, SWP_SHOWWINDOW)
    b = grab()
    d = np.abs(a.astype(np.int16)-b.astype(np.int16)).sum(2)
    print(f"iter {i}: gamefocus={u32.GetForegroundWindow()==h} motion={100*(d>30).mean():.2f}%")
    Image.fromarray(b).save("interact_last.png")
    time.sleep(0.15)
print("saved interact_last.png")
