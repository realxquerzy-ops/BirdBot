import time
import numpy as np
from PIL import Image
import gd_run as g, ocr_mod
from bg_cap import grab_print

def ocr_center(arr, x0=600, y0=300, x1=1400, y1=800):
    img = Image.fromarray(arr).crop((x0, y0, x1, y1))
    img = img.resize((img.width*2, img.height*2), Image.LANCZOS)
    a = np.asarray(img.convert("L"))
    inv = 255 - np.where(a > max(100, int(np.percentile(a, 60))), 255, 0).astype(np.uint8)
    return ocr_mod.ocr_img(Image.fromarray(inv))

if __name__ == "__main__":
    H = g.find_gl()
    arr, _ = grab_print(H)
    print("BEFORE OCR:", repr(ocr_center(arr)), flush=True)
    g.send_key(H, 0x20); time.sleep(0.6)
    arr, _ = grab_print(H)
    s = ocr_center(arr)
    print("AFTER SPACE:", repr(s), flush=True)
    Image.fromarray(arr).save("after_space.png")