import ctypes
from ctypes import wintypes
import numpy as np
from PIL import Image
import gd_run as g, ocr_mod

u32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", ctypes.c_long),
                ("biHeight", ctypes.c_long), ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", ctypes.c_long),
                ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD)]

def grab_print(h):
    r = g.win_rect(h); w = r[2]-r[0]; hh = r[3]-r[1]
    hdc = u32.GetWindowDC(h)
    mdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, hh)
    old = gdi32.SelectObject(mdc, bmp)
    PW_RENDERFULLCONTENT = 2
    ok = u32.PrintWindow(h, mdc, PW_RENDERFULLCONTENT)
    bmi = BITMAPINFOHEADER(); bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.biWidth = w; bmi.biHeight = -hh; bmi.biPlanes = 1; bmi.biBitCount = 32; bmi.biCompression = 0
    buf = ctypes.create_string_buffer(w*hh*4)
    got = gdi32.GetDIBits(mdc, bmp, 0, hh, buf, ctypes.byref(bmi), 0)
    gdi32.SelectObject(mdc, old)
    gdi32.DeleteObject(bmp); gdi32.DeleteDC(mdc); u32.ReleaseDC(h, hdc)
    if got:
        arr = np.frombuffer(buf, dtype=np.uint8).reshape(hh, w, 4)
        return np.ascontiguousarray(arr[:, :, [2, 1, 0]]), ok
    return None, ok

if __name__ == "__main__":
    H = g.find_gl()
    print("hwnd", H, "rect", g.win_rect(H), flush=True)
    arr, ok = grab_print(H)
    print("PrintWindow ok:", ok, "arr:", None if arr is None else arr.shape, flush=True)
    if arr is not None:
        Image.fromarray(arr).save("print_cap.png")
        a = np.asarray(Image.fromarray(arr).crop((0, 0, 500, 300)).convert("L"))
        inv = 255 - np.where(a > max(110, int(np.percentile(a, 70))), 255, 0).astype(np.uint8)
        s = ocr_mod.ocr_img(Image.fromarray(inv))
        print("OCR:", repr(s), flush=True)