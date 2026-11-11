import ctypes, time
from ctypes import wintypes

u32 = ctypes.windll.user32

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010

SW, SH = u32.GetSystemMetrics(0), u32.GetSystemMetrics(1)

def move(x, y):
    nx = int(x * 65535 / (SW - 1)); ny = int(y * 65535 / (SH - 1))
    u32.mouse_event(MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE, nx, ny, 0, 0)

def click(x=None, y=None, button="left", double=False):
    if x is not None:
        move(x, y); time.sleep(0.05)
    down, up = (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP) if button == "left" else (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP)
    u32.mouse_event(down, 0, 0, 0, 0); time.sleep(0.03); u32.mouse_event(up, 0, 0, 0, 0)
    if double:
        time.sleep(0.06); u32.mouse_event(down, 0, 0, 0, 0); time.sleep(0.03); u32.mouse_event(up, 0, 0, 0, 0)

def pos():
    pt = wintypes.POINT(); u32.GetCursorPos(ctypes.byref(pt)); return (pt.x, pt.y)

if __name__ == "__main__":
    print("screen", SW, SH)
    p0 = pos(); print("start", p0)
    move(960, 540); time.sleep(0.15); print("moved ->", pos(), "(expect ~960,540)")
    move(p0[0], p0[1]); time.sleep(0.15); print("restored ->", pos())
