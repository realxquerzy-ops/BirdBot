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

def win_rect(h):
    r = wintypes.RECT(); u32.GetWindowRect(h, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom

def top(h):
    u32.ShowWindow(h, 9); focus(h); u32.SetWindowPos(h, HWND_TOPMOST, 0, 0, 1920, 1080, SWP_SHOWWINDOW)

def gentle_top(h):
    u32.ShowWindow(h, 9); focus(h)

def grab(rect=None):
    if rect is None: rect = (0, 0, 1920, 1080)
    return np.asarray(ImageGrab.grab(bbox=rect, all_screens=True).convert("RGB"))

def grab_win(h, rect=None):
    if rect is None: rect = win_rect(h)
    return np.asarray(ImageGrab.grab(bbox=rect, all_screens=True).convert("RGB")), rect

def tap(vk, hold=0.0):
    u32.keybd_event(vk, 0, 0, 0)
    if hold: time.sleep(hold)
    u32.keybd_event(vk, 0, 2, 0)

WM_KEYDOWN = 0x0100; WM_KEYUP = 0x0101; WM_CHAR = 0x0102

def send_key(h, vk, hold=0.0, lparam=1):
    u32.PostMessageW(h, WM_KEYDOWN, vk, lparam)
    if hold: time.sleep(hold)
    u32.PostMessageW(h, WM_KEYUP, vk, lparam)

def read_state(frame):
    crop = Image.fromarray(frame).crop((0, 0, 340, 1080))
    crop = crop.resize((crop.width*2, crop.height*2), Image.LANCZOS)
    g = np.asarray(crop.convert("L"))
    inv = 255 - np.where(g > max(110, int(np.percentile(g, 70))), 255, 0).astype(np.uint8)
    txt = ocr_mod.ocr_img(Image.fromarray(inv))
    def num(pat):
        m = re.search(pat, txt)
        return float(m.group(1)) if m else None
    return {
        "time": num(r"Time[:\s]*([0-9]+\.[0-9]+)"),
        "attempt": num(r"Attempt[:\s]*([0-9]+)"),
        "x": num(r"[xX][:\s]*([0-9]+)"),
        "y": num(r"[Yy][:\s]*([0-9]+)"),
        "taps": num(r"Taps[:\s]*([0-9]+)"),
        "warp": num(r"Time\s*Harp[:\s]*([0-9]+)"),
    }

def measure(jumps, duration, poll=0.18, log=None):
    global H
    H = find_gl(); top(H); time.sleep(0.2)
    tap(VK_R); time.sleep(0.35)
    top(H)
    t0 = time.time()
    jumped = [False]*len(jumps)
    maxT = 0.0; last = None; events = []
    next_poll = 0.0
    while time.time() - t0 < duration:
        el = time.time() - t0
        for i, j in enumerate(jumps):
            if not jumped[i] and el >= j:
                tap(VK_SPACE); jumped[i] = True; events.append((round(el,2), "jump"))
        if el >= next_poll:
            top(H)
            st = read_state(grab())
            next_poll = el + poll
            if log is not None:
                log.append((round(el,2), st))
            if st["time"] is not None:
                if st["time"] > maxT: maxT = st["time"]
                if last is not None and st["time"] < last - 0.4:
                    events.append((round(el,2), f"death@~{last}"))
                    break
                last = st["time"]
        time.sleep(0.004)
    return maxT, events

if __name__ == "__main__":
    jumps = [float(x) for x in sys.argv[1].split(",")] if len(sys.argv) > 1 and sys.argv[1] else []
    dur = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
    log = []
    mt, ev = measure(jumps, dur, log=log)
    print(f"jumps={jumps} -> maxTime={mt:.2f}")
    print("events:", ev)
    print("samples:")
    for e, s in log:
        print(f"  t={e:4.2f}  Time={s['time']} x={s['x']} y={s['y']} attempt={s['attempt']}")
