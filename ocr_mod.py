import asyncio, os, tempfile
from winsdk.windows.media.ocr import OcrEngine
from winsdk.windows.storage import StorageFile, FileAccessMode
from winsdk.windows.graphics.imaging import BitmapDecoder
from PIL import Image

_engine = OcrEngine.try_create_from_user_profile_languages()
print("engine lang:", _engine.recognizer_language.language_tag)

async def _ocr(path):
    f = await StorageFile.get_file_from_path_async(os.path.abspath(path))
    s = await f.open_async(FileAccessMode.READ)
    dec = await BitmapDecoder.create_async(s)
    bmp = await dec.get_software_bitmap_async()
    res = await _engine.recognize_async(bmp)
    return res.text

def ocr_img(pil_img):
    tmp = os.path.join(tempfile.gettempdir(), "_gdocr.png")
    pil_img.save(tmp)
    return asyncio.run(_ocr(tmp))

if __name__ == "__main__":
    import sys, time
    p = sys.argv[1] if len(sys.argv) > 1 else "labels_bw.png"
    t = time.time()
    print("result:", ocr_img(Image.open(p)))
    print(f"took {time.time()-t:.2f}s")
