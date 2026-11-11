import ctypes, sys, time
from ctypes import wintypes
from PIL import ImageGrab

u32 = ctypes.windll.user32
k32 = ctypes.windll.kernel32

TITLE = "Geometry Dash"

def find_game():
    hwnd = u32.FindWindowW(None, TITLE)
    if not hwnd:
        raise SystemExit("Geometry Dash window not found")
    return hwnd

def force_focus(hwnd):
    u32.ShowWindow(hwnd, 9)  # SW_RESTORE
    time.sleep(0.2)
    # foreground unlock trick
    fg = u32.GetForegroundWindow()
    tid_fg = u32.GetWindowThreadProcessId(fg, None)
    tid_me = k32.GetCurrentThreadId()
    u32.AttachThreadInput(tid_me, tid_fg, True)
    u32.SetForegroundWindow(hwnd)
    u32.BringWindowToTop(hwnd)
    u32.AttachThreadInput(tid_me, tid_fg, False)
    time.sleep(0.3)

def rect(hwnd):
    r = wintypes.RECT()
    u32.GetWindowRect(hwnd, ctypes.byref(r))
    return (r.left, r.top, r.right, r.bottom)

def main():
    hwnd = find_game()
    force_focus(hwnd)
    box = rect(hwnd)
    print("hwnd", hwnd, "rect", box, "size", box[2]-box[0], box[3]-box[1])
    img = ImageGrab.grab(bbox=box, all_screens=True)
    out = sys.argv[1] if len(sys.argv) > 1 else "frame.png"
    img.save(out)
    print("saved", out, img.size)

if __name__ == "__main__":
    main()
