import os
import re
import sys
import json
import asyncio
import subprocess
import fitz
import edge_tts
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv

# Paths & Configuration
PDF_PATH = "/Users/mac/Downloads/Necklaces of Gems Shaikh Muhammad ibn Yahya at-Tafidi.pdf"
IMAGE_DIR = "images"
AUDIO_DIR = "temp_audio"
VIDEO_DIR = "videos"
PROGRESS_FILE = "cloudinary_videos.json"
VOICE = "en-US-ChristopherNeural"  # High quality male English voice
CONCURRENCY = 4

START_PAGE = 24
END_PAGE = 580
START_VIDEO_INDEX = 898  # 898.mp4 corresponds to PDF page 24

os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)
os.makedirs(IMAGE_DIR, exist_ok=True)

# Load environment & configure Cloudinary
load_dotenv(".env")

def clean_val(val):
    return val.strip().strip("'").strip('"') if val else ""

cloud_name = clean_val(os.getenv("CLOUDINARY_CLOUD_NAME"))
api_key = clean_val(os.getenv("CLOUDINARY_APP_ID") or os.getenv("CLOUDINARY_API_KEY"))
api_secret = clean_val(os.getenv("CLOUDINARY_APP_SECRET") or os.getenv("CLOUDINARY_API_SECRET"))

cloudinary.config(
    cloud_name=cloud_name,
    api_key=api_key,
    api_secret=api_secret,
    secure=True
)
print(f"✓ Cloudinary configured for cloud_name: '{cloud_name}'")

# Open PDF document
doc = fitz.open(PDF_PATH)
total_pdf_pages = len(doc)

json_lock = asyncio.Lock()

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_progress(progress):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)

def clean_pdf_text(raw_text):
    if not raw_text:
        return ""
    
    # Remove running header patterns like 'Necklaces of Gems       123\n' or '123\nNecklaces of Gems       123\n' or 'xxiii\n    xxiii\n'
    text = re.sub(r'(?i)^\s*[a-z0-9ivxlcdm]+\s*\n(\s*[a-z0-9ivxlcdm]+\s*\n)?', '', raw_text)
    text = re.sub(r'(?i)Necklaces\s+of\s+Gems\s+(\d+|[ivxlcdm]+)?\s*\n', '', text)
    text = re.sub(r'(?i)^\s*(\d+|[ivxlcdm]+)\s*\n', '', text)
    
    # Map special transliteration characters to clean English text for natural TTS pronunciation
    replacements = {
        '¥': 'h', 'º': 'i', '«': 'u', '‹': "'", '›': "'", 'å': 'a', '£': 't', 'ª': 'h',
        'ƒ': 's', '—': '-', '–': '-', '‘': "'", '’': "'", '“': '"', '”': '"',
        '…': '...', '—': '-'
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
        
    # Fix hyphenated words at line breaks
    text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)
    
    # Clean up line breaks into readable sentences
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return ' '.join(lines)

async def upload_video_to_cloudinary(file_id, video_path):
    # Check if already uploaded
    progress = load_progress()
    if file_id in progress:
        print(f"[{file_id}] Already in Cloudinary: {progress[file_id]['download_url']}", flush=True)
        return True

    for attempt in range(1, 6):
        try:
            # Run upload in worker thread to prevent blocking event loop
            res = await asyncio.to_thread(
                cloudinary.uploader.upload,
                video_path,
                resource_type="video",
                folder="dawah_videos",
                public_id=f"dawah_video_{file_id}",
                overwrite=True
            )

            secure_url = res.get("secure_url")
            public_id = res.get("public_id")

            async with json_lock:
                current_progress = load_progress()
                current_progress[file_id] = {
                    "public_id": public_id,
                    "download_url": secure_url,
                    "bytes": res.get("bytes"),
                    "duration": res.get("duration"),
                    "format": res.get("format")
                }
                save_progress(current_progress)

            print(f"  ✓ [{file_id}] Uploaded to Cloudinary! URL: {secure_url}", flush=True)
            return True

        except Exception as e:
            print(f"[{file_id}] Cloudinary upload attempt {attempt}/5 failed: {e}", flush=True)
            if attempt < 5:
                await asyncio.sleep(attempt * 3)

    return False

async def process_page(page_num, video_idx, semaphore):
    async with semaphore:
        file_id = f"{video_idx:03d}"
        img_name = f"{file_id}.jpg"
        audio_name = f"{file_id}.mp3"
        video_name = f"{file_id}.mp4"

        img_path = os.path.join(IMAGE_DIR, img_name)
        audio_path = os.path.join(AUDIO_DIR, audio_name)
        video_path = os.path.join(VIDEO_DIR, video_name)

        pdf_page_idx = page_num - 1  # 0-indexed PyMuPDF
        page = doc[pdf_page_idx]

        # Check if video already exists and is valid using ffprobe
        video_ready = False
        if os.path.exists(video_path):
            check_proc = await asyncio.create_subprocess_exec(
                "/opt/homebrew/bin/ffprobe", "-v", "error", video_path,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            await check_proc.wait()
            if check_proc.returncode == 0 and os.path.getsize(video_path) > 10240:
                print(f"[{file_id}] Video verified valid: {video_name}", flush=True)
                video_ready = True

        if not video_ready:
            try:
                # 1. Extract and clean text
                raw_text = page.get_text()
                text = clean_pdf_text(raw_text)

                if len(text.strip()) < 10:
                    text = f"Necklaces of Gems by Shaikh Muhammad ibn Yahya at-Tadifi. Page {page_num}."

                # 2. Render image (150 dpi for video frame)
                pix = page.get_pixmap(dpi=150)
                pix.save(img_path)

                # 3. High quality male English TTS audio generation with retry
                tts_success = False
                for tts_attempt in range(1, 6):
                    try:
                        communicate = edge_tts.Communicate(text, VOICE)
                        await communicate.save(audio_path)
                        if os.path.exists(audio_path) and os.path.getsize(audio_path) > 500:
                            tts_success = True
                            break
                    except Exception as tts_err:
                        print(f"[{file_id}] TTS attempt {tts_attempt}/5 failed: {tts_err}. Retrying...", flush=True)
                        await asyncio.sleep(tts_attempt * 2)

                if not tts_success:
                    print(f"[{file_id}] Failed to generate audio after 5 attempts.", flush=True)
                    return False

                # 4. FFmpeg video creation
                ffmpeg_cmd = [
                    "/opt/homebrew/bin/ffmpeg",
                    "-y",
                    "-loop", "1",
                    "-i", img_path,
                    "-i", audio_path,
                    "-c:v", "libx264",
                    "-tune", "stillimage",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-pix_fmt", "yuv420p",
                    "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                    "-shortest",
                    video_path
                ]

                proc = await asyncio.create_subprocess_exec(
                    *ffmpeg_cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                await proc.wait()

                if proc.returncode != 0 or not os.path.exists(video_path):
                    print(f"[{file_id}] FFmpeg error on exit code {proc.returncode}", flush=True)
                    return False

                size_mb = os.path.getsize(video_path) / (1024 * 1024)
                print(f"[{file_id}] Rendered {video_name} (PDF pg {page_num}) - {size_mb:.2f} MB", flush=True)

            except Exception as e:
                print(f"[{file_id}] Error processing PDF page {page_num}: {e}", flush=True)
                return False

        # 5. Upload to Cloudinary
        upload_success = await upload_video_to_cloudinary(file_id, video_path)
        return upload_success

async def main():
    semaphore = asyncio.Semaphore(CONCURRENCY)
    
    pages = list(range(START_PAGE, END_PAGE + 1))
    total_videos = len(pages)
    end_video_idx = START_VIDEO_INDEX + total_videos - 1
    
    print(f"\n=======================================================")
    print(f"Starting Video Generation & Cloudinary Upload: Necklaces of Gems")
    print(f"PDF Pages: {START_PAGE} to {END_PAGE} ({total_videos} total)")
    print(f"Video Range: {START_VIDEO_INDEX:03d}.mp4 to {end_video_idx:03d}.mp4")
    print(f"Voice: {VOICE}")
    print(f"Target: Parallel Video Creation + Direct Cloudinary Upload")
    print(f"=======================================================\n", flush=True)

    tasks = [process_page(page_num, START_VIDEO_INDEX + i, semaphore) for i, page_num in enumerate(pages)]
    results = await asyncio.gather(*tasks)

    successful = sum(1 for r in results if r)
    print(f"\n=======================================================")
    print(f"Necklaces of Gems Batch Complete: {successful}/{total_videos} videos generated and uploaded.")
    print(f"=======================================================\n")

if __name__ == "__main__":
    asyncio.run(main())
