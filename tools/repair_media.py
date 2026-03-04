import os
import imghdr
import shutil

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'post_images')

def detect_ext(path):
    try:
        t = imghdr.what(path)
        if t:
            return '.' + t
        with open(path, 'rb') as f:
            h = f.read(64)
            if h.startswith(b'\xFF\xD8'):
                return '.jpg'
            if b'WEBP' in h:
                return '.webp'
            if h[:4] == b'RIFF' and b'WAVE' in h:
                return '.wav'
            if b'ftyp' in h or h[:4] == b'\x00\x00\x00\x18':
                return '.mp4'
    except Exception:
        pass
    return None

def main():
    if not os.path.isdir(STATIC_DIR):
        print("Klasör bulunamadı:", STATIC_DIR)
        return
    for fname in os.listdir(STATIC_DIR):
        if not fname.lower().endswith('.txt'):
            continue
        full = os.path.join(STATIC_DIR, fname)
        ext = detect_ext(full)
        if ext:
            newname = fname[:-4] + ext
            newfull = os.path.join(STATIC_DIR, newname)
            if os.path.exists(newfull):
                print("Hedef zaten var, atlanıyor:", newname)
                continue
            shutil.move(full, newfull)
            print("Yeniden adlandırıldı:", fname, "->", newname)
        else:
            print("Uzantı belirlenemedi:", fname)

if __name__ == '__main__':
    main()
