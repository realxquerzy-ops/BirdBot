import ctypes, sys
from ctypes import wintypes
import numpy as np
from PIL import Image

u32 = ctypes.windll.user32
g32 = ctypes.windll.gdi32

class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", ctypes.c_long), ("biYPelsPerMeter", ctypes.c_long),
                ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]

def print_window(hwnd):
    r = wintypes.RECT(); u32.GetClientRect(hwnd, ctypes.byref(r))
    w, h = r.right, r.bottom
    if w <= 0 or h <= 0:
        u32.GetWindowRect(hwnd, ctypes.byref(r)); w, h = r.right - r.left, r.bottom - r.top
    hdc = u32.GetWindowDC(hwnd)
    mdc = g32.CreateCompatibleDC(hdc)
    bmp = g32.CreateCompatibleBitmap(hdc, w, h)
    g32.SelectObject(mdc, bmp)
    ok = u32.PrintWindow(hwnd, mdc, 2)  # PW_RENDERFULLCONTENT
    bi = BITMAPINFOHEADER(); bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.biWidth = w; bi.biHeight = -h; bi.biPlanes = 1; bi.biBitCount = 32; bi.biCompression = 0
    buf = ctypes.create_string_buffer(w * h * 4)
    g32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
    arr = np.frombuffer(buf, np.uint8).reshape(h, w, 4)[..., [2, 1, 0]]
    g32.DeleteObject(bmp); g32.DeleteDC(mdc); u32.ReleaseDC(hwnd, hdc)
    return ok, arr

hwnd = u32.FindWindowW(None, "Geometry Dash")
print("hwnd", hwnd)
ok, arr = print_window(hwnd)
print("PrintWindow ok:", ok, "shape:", arr.shape, "mean:", arr.mean())
out = sys.argv[1] if len(sys.argv) > 1 else "pw.png"
Image.fromarray(arr).save(out)
print("saved", out)
