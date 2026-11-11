import json
import numpy as np
from PIL import Image
import gd_run as g, ocr_mod

H = g.find_gl()
r = g.win_rect(H)
print("hwnd", H, "rect", r, flush=True)
frm, _ = g.grab_win(H, r)
Image.fromarray(frm).save("bg_probe.png")
crop = Image.fromarray(frm).crop((0, 0, min(500, r[2]-r[0]), min(300, r[3]-r[1])))
crop = crop.resize((crop.width*2, crop.height*2), Image.LANCZOS)
a = np.asarray(crop.convert("L"))
inv = 255 - np.where(a > max(110, int(np.percentile(a, 70))), 255, 0).astype(np.uint8)
s = ocr_mod.ocr_img(Image.fromarray(inv))
print("OCR:", repr(s), flush=True)
# save inverted crop too
Image.fromarray(inv).save("bg_inv.png")