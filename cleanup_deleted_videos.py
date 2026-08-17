import os
import sys
import json
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv

PROGRESS_FILE = "cloudinary_videos.json"
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

if not os.path.exists(PROGRESS_FILE):
    print("No cloudinary_videos.json found.")
    sys.exit(0)

with open(PROGRESS_FILE, "r") as f:
    data = json.load(f)

print(f"Total records in {PROGRESS_FILE}: {len(data)}")

deleted_keys = []
for key in list(data.keys()):
    # Key could be "1", "001", "898", etc.
    try:
        num = int(key)
        f_p3 = f"videos/{num:03d}.mp4"
        f_raw = f"videos/{key}.mp4"
        
        exists = os.path.exists(f_p3) or os.path.exists(f_raw)
        if not exists:
            deleted_keys.append(key)
    except Exception as e:
        print(f"Error checking key {key}: {e}")

print(f"\nFound {len(deleted_keys)} deleted video entries in local videos/ folder:")
for k in deleted_keys:
    print(f"  - Key: {k}, Public ID: {data[k].get('public_id')}, URL: {data[k].get('download_url')}")

if not deleted_keys:
    print("\nNo deleted videos found! Everything is in sync.")
    sys.exit(0)

print(f"\nDeleting {len(deleted_keys)} video(s) from Cloudinary...")
removed_from_cloudinary = 0
for k in deleted_keys:
    entry = data[k]
    pub_id = entry.get("public_id")
    if pub_id:
        try:
            res = cloudinary.uploader.destroy(pub_id, resource_type="video")
            print(f"  ✓ Deleted from Cloudinary: {pub_id} -> Result: {res.get('result')}")
            removed_from_cloudinary += 1
        except Exception as err:
            print(f"  ✗ Error deleting {pub_id} from Cloudinary: {err}")
    
    # Remove from JSON registry
    del data[k]

with open(PROGRESS_FILE, "w") as f:
    json.dump(data, f, indent=2)

print(f"\n=======================================================")
print(f"Cleaned up {len(deleted_keys)} entries.")
print(f"Updated {PROGRESS_FILE} (Remaining records: {len(data)})")
print(f"=======================================================")
