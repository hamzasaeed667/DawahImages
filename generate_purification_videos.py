import os
import re
import sys
import asyncio
import subprocess
import fitz
import edge_tts

# Paths & Configuration
PDF_PATH = "/Users/mac/Downloads/Purification of the mind by Qadir al-Jilani.pdf"
IMAGE_DIR = "images"
AUDIO_DIR = "temp_audio"
VIDEO_DIR = "videos"
VOICE = "en-US-ChristopherNeural"  # High quality male English voice
CONCURRENCY = 2

START_PAGE = 11
END_PAGE = 179
START_VIDEO_INDEX = 456  # 456.mp4 corresponds to PDF page 11

os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)

# Open PDF document
doc = fitz.open(PDF_PATH)
total_pdf_pages = len(doc)

def clean_pdf_text(raw_text):
    if not raw_text:
        return ""
    # Remove standalone page numbers at top (e.g. '9\n9\n' or '10\n10\n')
    text = re.sub(r'^\s*\d+\s*\n\s*\d+\s*\n', '', raw_text)
    
    # Map special transliteration characters to clean English text
    replacements = {
        '¥': 'h', 'º': 'i', '«': 'u', '‹': "'", 'å': 'a', '£': 't', 'ª': 'h',
        '—': '-', '‘': "'", '’': "'", '“': '"', '”': '"'
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
        
    # Fix hyphenated words at line breaks
    text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)
    
    # Clean up line breaks into readable sentences
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return ' '.join(lines)

async def process_video(page_num, video_idx, semaphore):
    async with semaphore:
        file_id = f"{video_idx:03d}"
        img_name = f"{file_id}.jpg"
        audio_name = f"{file_id}.mp3"
        video_name = f"{file_id}.mp4"

        img_path = os.path.join(IMAGE_DIR, img_name)
        audio_path = os.path.join(AUDIO_DIR, audio_name)
        video_path = os.path.join(VIDEO_DIR, video_name)

        pdf_page_idx = page_num - 1  # 0-indexed PyMuPDF

        # Check if video already exists and is valid using ffprobe
        if os.path.exists(video_path):
            check_proc = await asyncio.create_subprocess_exec(
                "/opt/homebrew/bin/ffprobe", "-v", "error", video_path,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            await check_proc.wait()
            if check_proc.returncode == 0 and os.path.getsize(video_path) > 10240:
                print(f"[{file_id}] Video verified valid, skipping: {video_name}", flush=True)
                return True

        try:
            # 1. Extract text from PDF page
            page = doc[pdf_page_idx]
            raw_text = page.get_text()
            text = clean_pdf_text(raw_text)

            if len(text.strip()) < 5:
                text = f"Purification of the Mind. Page {page_num}."

            # 2. Render image if not existing
            if not os.path.exists(img_path):
                pix = page.get_pixmap(dpi=150)
                pix.save(img_path)

            # 3. High quality male English TTS audio generation with retry logic
            tts_success = False
            for tts_attempt in range(1, 6):
                try:
                    communicate = edge_tts.Communicate(text, VOICE)
                    await communicate.save(audio_path)
                    tts_success = True
                    break
                except Exception as tts_err:
                    print(f"[{file_id}] TTS attempt {tts_attempt}/5 failed: {tts_err}. Retrying...", flush=True)
                    await asyncio.sleep(tts_attempt * 3)
            
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

            if proc.returncode == 0 and os.path.exists(video_path):
                size_mb = os.path.getsize(video_path) / (1024 * 1024)
                print(f"[{file_id}] Rendered {video_name} (PDF pg {page_num}) - {size_mb:.2f} MB", flush=True)
                return True
            else:
                print(f"[{file_id}] FFmpeg error on exit code {proc.returncode}", flush=True)
                return False

        except Exception as e:
            print(f"[{file_id}] Error processing PDF page {page_num}: {e}", flush=True)
            return False

async def main():
    semaphore = asyncio.Semaphore(CONCURRENCY)
    
    pages = list(range(START_PAGE, END_PAGE + 1))
    tasks = [process_video(page_num, START_VIDEO_INDEX + i, semaphore) for i, page_num in enumerate(pages)]
    
    total_videos = len(tasks)
    end_video_idx = START_VIDEO_INDEX + total_videos - 1
    print(f"\n=======================================================")
    print(f"Starting Video Generation for 'Purification of the mind'")
    print(f"PDF Pages: {START_PAGE} to {END_PAGE}")
    print(f"Video Output Range: {START_VIDEO_INDEX:03d}.mp4 to {end_video_idx:03d}.mp4")
    print(f"Voice: Male English ({VOICE})")
    print(f"=======================================================\n")

    results = await asyncio.gather(*tasks)

    successful = sum(1 for r in results if r)
    print(f"\n=======================================================")
    print(f"Batch Video Generation Complete: {successful}/{total_videos} videos created.")
    print(f"=======================================================")

if __name__ == "__main__":
    asyncio.run(main())
