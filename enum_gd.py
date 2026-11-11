import ctypes
from ctypes import wintypes

u32 = ctypes.windll.user32
PID = 31200

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
GW_OWNER = 4

def title(h):
    n = u32.GetWindowTextLengthW(h)
    b = ctypes.create_unicode_buffer(n + 1)
    u32.GetWindowTextW(h, b, n + 1)
    return b.value

def cls(h):
    b = ctypes.create_unicode_buffer(256)
    u32.GetClassNameW(h, b, 256)
    return b.value

rows = []
def cb(h, l):
    pid = wintypes.DWORD()
    u32.GetWindowThreadProcessId(h, ctypes.byref(pid))
    if pid.value == PID:
        r = wintypes.RECT(); u32.GetWindowRect(h, ctypes.byref(r))
        rows.append((h, cls(h), title(h), u32.IsWindowVisible(h),
                     (r.left, r.top, r.right - r.left, r.bottom - r.top)))
    return True

u32.EnumWindows(WNDENUMPROC(cb), 0)
print(f"windows for pid {PID}:")
for h, c, t, v, rc in rows:
    print(f"  hwnd={h} class={c!r} vis={v} rect={rc} title={t!r}")
