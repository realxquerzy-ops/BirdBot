"""Core helpers for the GD code-vision bot (capture / input / state)."""
import time
import ctypes
from ctypes import wintypes
import numpy as np
from PIL import ImageGrab, Image

u32 = ctypes.windll.user32
k32 = ctypes.windll.kernel32

HWND_TOP = 0
SWP_SHOWWINDOW = 0x40
SWP_FRAMECHANGED = 0x20
VK_SPACE = 0x20
KEYEVENTF_KEYUP = 0x0002
INPUT_KEYBOARD = 1

# ---------- input ----------
ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]

class _INPUTunion(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT)]

class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTunion)]

def _send(vk, up=False):
    inp = INPUT(type=INPUT_KEYBOARD,
                u=_INPUTunion(ki=KEYBDINPUT(wVk=vk, wScan=0,
                                            dwFlags=KEYEVENTF_KEYUP if up else 0,
                                            time=0, dwExtraInfo=0)))
    u32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

def key_down(vk=VK_SPACE):
    _send(vk, up=False)

def key_up(vk=VK_SPACE):
    _send(vk, up=True)

def tap(vk=VK_SPACE, hold=0.0):
    key_down(vk)
    if hold > 0:
        time.sleep(hold)
    key_up(vk)

def hold(vk, seconds):
    key_down(vk); time.sleep(seconds); key_up(vk)

# ---------- window ----------
def find_window(title="Geometry Dash"):
    h = u32.FindWindowW(None, title)
    if not h:
        raise RuntimeError(f"window not found: {title}")
    return h

def force_fullscreen(h, w=1920, hgt=1080):
    u32.ShowWindow(h, 9)
    time.sleep(0.15)
    u32.ShowWindow(h, 3)
    time.sleep(0.15)
    u32.SetWindowPos(h, HWND_TOP, 0, 0, w, hgt, SWP_SHOWWINDOW | SWP_FRAMECHANGED)
    time.sleep(0.15)
    fg = u32.GetForegroundWindow()
    u32.AttachThreadInput(k32.GetCurrentThreadId(), u32.GetWindowThreadProcessId(fg, None), True)
    u32.SetForegroundWindow(h)
    u32.BringWindowToTop(h)
    u32.AttachThreadInput(k32.GetCurrentThreadId(), u32.GetWindowThreadProcessId(fg, None), False)
    return fg

def keep_on_top(h, w=1920, hgt=1080):
    u32.SetWindowPos(h, HWND_TOP, 0, 0, w, hgt, SWP_SHOWWINDOW)

def window_rect(h):
    r = wintypes.RECT(); u32.GetWindowRect(h, ctypes.byref(r))
    return (r.left, r.top, r.right, r.bottom)

def focused(h):
    return u32.GetForegroundWindow() == h

# ---------- capture ----------
def grab(h=None, box=None):
    if box is None:
        box = window_rect(h) if h else None
    return np.asarray(ImageGrab.grab(bbox=box, all_screens=True).convert("RGB"))

def changed_pct(a, b, thr=30):
    if a.shape != b.shape:
        return 100.0, (0, 0, 0, 0)
    d = np.abs(a.astype(np.int16) - b.astype(np.int16)).sum(2)
    ch = d > thr
    pct = 100.0 * ch.mean()
    ys, xs = np.where(ch)
    bb = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())) if len(xs) else (0, 0, 0, 0)
    return pct, bb

def is_static(a, b, thr=30, pct_thresh=0.5):
    return changed_pct(a, b, thr)[0] < pct_thresh
