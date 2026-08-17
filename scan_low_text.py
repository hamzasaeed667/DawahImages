import os
import subprocess
from concurrent.futures import ThreadPoolExecutor

all_imgs = sorted(
    [f for f in os.listdir('images') if f.endswith('.jpg')],
    key=lambda x: int(os.path.splitext(x)[0]) if os.path.splitext(x)[0].isdigit() else 999999
)

def process_img(img):
    fpath = os.path.join('images', img)
    try:
        res = subprocess.run(
            ['/opt/homebrew/bin/tesseract', fpath, 'stdout', '-l', 'eng', '--oem', '1', '--psm', '6'],
            capture_output=True,
            text=True
        )
        text = ' '.join(res.stdout.split())
        words = text.split()
        return (img, len(words), text)
    except Exception as e:
        return (img, -1, str(e))

if __name__ == '__main__':
    print(f"Scanning {len(all_imgs)} images with 10 threads...", flush=True)
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(process_img, all_imgs))

    low_text = [r for r in results if r[1] < 30]
    low_text.sort(key=lambda x: x[1])

    print(f"\n=======================================================")
    print(f"Scan Complete! Found {len(low_text)} image(s) with < 30 words:")
    print(f"=======================================================\n")

    for img, wc, txt in low_text:
        stem = os.path.splitext(img)[0]
        has_video = os.path.exists(f"videos/{stem}.mp4") or os.path.exists(f"videos/{int(stem):03d}.mp4" if stem.isdigit() else "")
        print(f"[{img}] Word Count: {wc} | Has Video in videos/: {has_video}")
        print(f"  Content: \"{txt}\"\n")
