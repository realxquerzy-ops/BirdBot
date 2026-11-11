import ctypes, time, re, sys
from ctypes import wintypes
import numpy as np
from PIL import ImageGrab, Image
import ocr_mod

u32 = ctypes.windll.user32
k32 = ctypes.windll.kernel32
HWND_TOPMOST = -1
SWP_SHOWWINDOW = 0x40
VK_SPACE = 0x20
VK_R = 0x52

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

def top(h):
    u32.ShowWindow(h, 9); focus(h); u32.SetWindowPos(h, HWND_TOPMOST, 0, 0, 1920, 1080, SWP_SHOWWINDOW)

def grab():
    return np.asarray(ImageGrab.grab(bbox=(0,0,1920,1080), all_screens=True).convert("RGB"))

def read_overlay(frame, scale=2):
    crop = Image.fromarray(frame).crop((0, 0, 300, 1080))
    crop = crop.resize((crop.width*scale, crop.height*scale), Image.LANCZOS)
    g = np.asarray(crop.convert("L"))
    inv = 255 - np.where(g > max(110, int(np.percentile(g, 70))), 255, 0).astype(np.uint8)
    txt = ocr_mod.ocr_img(Image.fromarray(inv))
    tm = re.search(r"Time[:\s]*([0-9]+\.[0-9]+)", txt)
    at = re.search(r"Attempt[:\s]*([0-9]+)", txt)
    return {"time": tm.group(1) if tm else None, "attempt": at.group(1) if at else None, "raw": txt}

h = find_gl()
top(h); time.sleep(0.3)
before = read_overlay(grab())
print("BEFORE:", before["time"], before["attempt"])
print("raw:", before["raw"][:200])

tap = lambda vk: (u32.keybd_event(vk,0,0,0), u32.keybd_event(vk,0,2,0))
tap(VK_R); time.sleep(0.4)
top(h)
start = time.time(); n = 0
while time.time() - start < 10:
    tap(VK_SPACE); n += 1
    time.sleep(0.04)
print(f"spammed {n} taps in 10s")
top(h); time.sleep(0.2)
after = read_overlay(grab())
print("AFTER:", after["time"], after["attempt"])
print("raw:", after["raw"][:200])
Image.fromarray(grab()).save("play_result.png")
