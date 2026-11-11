import ctypes, time, subprocess, re, sys
from ctypes import wintypes
import numpy as np
from PIL import ImageGrab, Image

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

def tap(vk, hold=0.0):
    u32.keybd_event(vk, 0, 0, 0)
    if hold: time.sleep(hold)
    u32.keybd_event(vk, 0, 2, 0)

def grab():
    return np.asarray(ImageGrab.grab(bbox=(0,0,1920,1080), all_screens=True).convert("RGB"))

def read_overlay():
    img = Image.fromarray(grab()).crop((0, 0, 260, 1080))
    img = img.resize((img.width*3, img.height*3), Image.LANCZOS)
    g = np.asarray(img.convert("L"))
    inv = 255 - np.where(g > max(110, int(np.percentile(g, 70))), 255, 0).astype(np.uint8)
    Image.fromarray(inv).save("_ov.png")
    out = subprocess.run(["powershell","-ExecutionPolicy","Bypass","-File","ocr_text.ps1","_ov.png"],
                         capture_output=True, text=True, encoding="utf-8", errors="ignore").stdout.strip()
    tm = re.search(r"Time[:\s]+([0-9]+\.[0-9]+)", out)
    at = re.search(r"Attempt[:\s]+([0-9]+)", out)
    pc = re.search(r"([0-9]+)\s*%", out)
    return (tm.group(1) if tm else "?", at.group(1) if at else "?", pc.group(1) if pc else "?", out)

h = find_gl()
top(h)
print("overlay before:", read_overlay()[:3])
tap(VK_R); time.sleep(0.3)
top(h)
start = time.time()
i = 0
last_report = 0
while time.time() - start < 16:
    tap(VK_SPACE)
    time.sleep(0.035)
    i += 1
    el = time.time() - start
    if el - last_report >= 2.0:
        top(h)
        t, a, p, _ = read_overlay()
        print(f"t={el:4.1f}s taps={i:4d}  Time={t}  Attempt={a}  Pct={p}")
        last_report = el
Image.fromarray(grab()).save("spam_result.png")
print("saved spam_result.png")
