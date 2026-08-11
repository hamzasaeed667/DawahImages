import os
import sys
import json
import time
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv

ENV_FILE = ".env"
PROGRESS_FILE = "cloudinary_videos.json"

load_dotenv(ENV_FILE)

def clean_val(val):
    if not val:
        return ""
    return val.strip().strip("'").strip('"')

def init_cloudinary():
    cloud_name = clean_val(os.getenv("CLOUDINARY_CLOUD_NAME"))
    api_key = clean_val(os.getenv("CLOUDINARY_APP_ID") or os.getenv("CLOUDINARY_API_KEY"))
    api_secret = clean_val(os.getenv("CLOUDINARY_APP_SECRET") or os.getenv("CLOUDINARY_API_SECRET"))

    if not cloud_name:
        print("Error: CLOUDINARY_CLOUD_NAME is not set in .env")
        print("Please add CLOUDINARY_CLOUD_NAME=<your_cloud_name> to .env")
        sys.exit(1)

    if not api_key or not api_secret:
        print("Error: CLOUDINARY_APP_ID or CLOUDINARY_APP_SECRET missing in .env")
        sys.exit(1)

    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True
    )
    print(f"✓ Cloudinary configured for cloud_name: '{cloud_name}'")

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_progress(progress):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)

def upload_all_videos(start_index=1, end_index=455):
    init_cloudinary()
    progress = load_progress()

    print(f"\n=======================================================")
    print(f"Starting Upload to Cloudinary ({start_index:03d} to {end_index:03d})")
    print(f"=======================================================\n")

    uploaded_in_run = 0

    for i in range(start_index, end_index + 1):
        file_id = f"{i:03d}"
        video_path = f"videos/{file_id}.mp4"

        if file_id in progress:
            print(f"[{file_id}] Already uploaded: {progress[file_id]['download_url']}")
            continue

        if not os.path.exists(video_path):
            print(f"[{file_id}] Warning: Video file missing: {video_path}")
            continue

        print(f"[{file_id}] Uploading {video_path} to Cloudinary...")

        success = False
        for attempt in range(1, 6):
            try:
                # Upload video to Cloudinary with resource_type='video'
                res = cloudinary.uploader.upload(
                    video_path,
                    resource_type="video",
                    folder="dawah_videos",
                    public_id=f"dawah_video_{file_id}",
                    overwrite=True
                )

                secure_url = res.get("secure_url")
                public_id = res.get("public_id")

                progress[file_id] = {
                    "public_id": public_id,
                    "download_url": secure_url,
                    "bytes": res.get("bytes"),
                    "duration": res.get("duration"),
                    "format": res.get("format")
                }

                save_progress(progress)
                uploaded_in_run += 1
                print(f"  ✓ Uploaded! Direct URL: {secure_url}", flush=True)
                success = True
                break

            except Exception as e:
                print(f"[{file_id}] Attempt {attempt}/5 failed: {e}", flush=True)
                if attempt < 5:
                    time.sleep(attempt * 3)

        if not success:
            print(f"[{file_id}] Permanent error after 5 attempts. Stopping batch.", flush=True)
            break

    print(f"\n=======================================================")
    print(f"Upload Batch Completed: {uploaded_in_run} videos uploaded in this run.")
    print(f"Total Cloudinary uploads so far: {len(progress)} / {end_index - start_index + 1}")
    print(f"Saved direct download links to: {PROGRESS_FILE}")
    print(f"=======================================================")

if __name__ == "__main__":
    upload_all_videos()
