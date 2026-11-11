from PIL import Image
import ocr_mod, time
img = Image.open("labels_bw.png")
for i in range(6):
    t0 = time.time()
    txt = ocr_mod.ocr_img(img)
    print(i, f"{time.time()-t0:.2f}s", len(txt), repr(txt[:70]))
