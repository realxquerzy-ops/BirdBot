from PIL import Image, ImageDraw, ImageFont
import ocr_mod

img = Image.new("RGB", (600, 120), (255, 255, 255))
d = ImageDraw.Draw(img)
try:
    f = ImageFont.truetype("arial.ttf", 48)
except Exception:
    f = ImageFont.load_default()
d.text((20, 30), "Time 12.34 Attempt 5", fill=(0, 0, 0), font=f)
img.save("_t.png")
print("plain:", repr(ocr_mod.ocr_img(img)))

# inverted (black bg, white text)
import numpy as np
a = 255 - np.asarray(img)
print("inverted:", repr(ocr_mod.ocr_img(Image.fromarray(a))))
