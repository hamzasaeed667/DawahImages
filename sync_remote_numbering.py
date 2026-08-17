import os
import sys
import json
import time
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv

PROGRESS_FILE = "cloudinary_videos.json"
load_dotenv(".env")

def clean_val(val):
    return val.strip().strip("'").strip('"') if val else ""

cloudinary.config(
    cloud_name=clean_val(os.getenv("CLOUDINARY_CLOUD_NAME")),
    api_key=clean_val(os.getenv("CLOUDINARY_APP_ID") or os.getenv("CLOUDINARY_API_KEY")),
    api_secret=clean_val(os.getenv("CLOUDINARY_APP_SECRET") or os.getenv("CLOUDINARY_API_SECRET")),
    secure=True
)

with open(PROGRESS_FILE, "r") as f:
    data = json.load(f)

print(f"Total records in {PROGRESS_FILE}: {len(data)}")

# Sort keys numerically (1 to 1446)
sorted_keys = sorted(data.keys(), key=lambda x: int(x))

renamed_count = 0
errors = []

for k in sorted_keys:
    key_num = int(k)
    current_entry = data[k]
    current_pub_id = current_entry.get("public_id")
    
    # Target public_id matching exact key
    # In earlier batches, 001..455 used dawah_video_001 or dawah_video_1?
    # Let's check format: 'dawah_videos/dawah_video_001' or 'dawah_videos/dawah_video_1'
    target_pub_id = f"dawah_videos/dawah_video_{key_num:03d}"
    
    # Also check if it was using 3-digit or unpadded
    if current_pub_id == target_pub_id:
        continue
        
    # Attempt Cloudinary rename
    try:
        res = cloudinary.uploader.rename(
            current_pub_id,
            target_pub_id,
            resource_type="video",
            overwrite=True
        )
        
        new_url = res.get("secure_url")
        new_pub_id = res.get("public_id")
        
        current_entry["public_id"] = new_pub_id
        current_entry["download_url"] = new_url
        if "bytes" in res:
            current_entry["bytes"] = res.get("bytes")
        if "duration" in res:
            current_entry["duration"] = res.get("duration")
        if "format" in res:
            current_entry["format"] = res.get("format")
            
        data[k] = current_entry
        renamed_count += 1
        print(f"[{k}] Renamed remote: {current_pub_id} -> {target_pub_id} | URL: {new_url}", flush=True)
        
        # Save progress every 20 items
        if renamed_count % 20 == 0:
            with open(PROGRESS_FILE, "w") as f:
                json.dump(data, f, indent=2)
                
    except Exception as err:
        print(f"[{k}] Error renaming {current_pub_id} -> {target_pub_id}: {err}", flush=True)
        errors.append((k, current_pub_id, target_pub_id, str(err)))

# Final save
with open(PROGRESS_FILE, "w") as f:
    json.dump(data, f, indent=2)

print(f"\n=======================================================")
print(f"Remote Renaming Complete: {renamed_count} assets renamed on Cloudinary.")
print(f"Errors encountered: {len(errors)}")
print(f"Updated {PROGRESS_FILE}")
print(f"=======================================================\n")
