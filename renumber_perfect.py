import os
import sys
import json
import shutil

PROGRESS_FILE = "cloudinary_videos.json"

# 1. Load Cloudinary JSON
if not os.path.exists(PROGRESS_FILE):
    print(f"Error: {PROGRESS_FILE} not found!")
    sys.exit(1)

with open(PROGRESS_FILE, "r") as f:
    cloud_data = json.load(f)

# Save backup
shutil.copyfile(PROGRESS_FILE, PROGRESS_FILE + ".bak")
print(f"Backed up {PROGRESS_FILE} to {PROGRESS_FILE}.bak")

# 2. Get list of existing video IDs sorted
video_files = [f for f in os.listdir("videos") if f.endswith(".mp4")]
video_nums = sorted([int(os.path.splitext(f)[0]) for f in video_files if os.path.splitext(f)[0].isdigit()])

print(f"Found {len(video_nums)} active videos on disk (Range: {video_nums[0]} to {video_nums[-1]}).")

# 3. Clean up extra images that don't belong to active videos
extra_img_count = 0
for f in os.listdir("images"):
    if f.endswith(".jpg"):
        stem = os.path.splitext(f)[0]
        if stem.isdigit():
            num = int(stem)
            if num not in video_nums:
                os.remove(os.path.join("images", f))
                extra_img_count += 1
print(f"Removed {extra_img_count} unused images from images/.")

# 4. Build Old -> New mapping (1-indexed contiguous)
mapping = {}
for new_idx, old_idx in enumerate(video_nums, start=1):
    mapping[old_idx] = new_idx

print(f"Built mapping: {len(mapping)} items (New Range: 1 to {len(mapping)}).")

# 5. Two-pass rename for videos/ to avoid collisions
temp_video_map = []
for old_idx, new_idx in mapping.items():
    old_file_3 = f"videos/{old_idx:03d}.mp4"
    old_file_raw = f"videos/{old_idx}.mp4"
    old_path = old_file_3 if os.path.exists(old_file_3) else old_file_raw
    
    tmp_path = f"videos/__tmp_{new_idx:03d}.mp4"
    final_path = f"videos/{new_idx:03d}.mp4"
    
    if os.path.exists(old_path):
        os.rename(old_path, tmp_path)
        temp_video_map.append((tmp_path, final_path))

for tmp_path, final_path in temp_video_map:
    os.rename(tmp_path, final_path)

print("✓ Renamed all video files in videos/ to sequential 001.mp4 -> 1446.mp4")

# 6. Two-pass rename for images/
temp_img_map = []
for old_idx, new_idx in mapping.items():
    old_file_3 = f"images/{old_idx:03d}.jpg"
    old_file_raw = f"images/{old_idx}.jpg"
    old_path = old_file_3 if os.path.exists(old_file_3) else old_file_raw
    
    tmp_path = f"images/__tmp_{new_idx:03d}.jpg"
    final_path = f"images/{new_idx:03d}.jpg"
    
    if os.path.exists(old_path):
        os.rename(old_path, tmp_path)
        temp_img_map.append((tmp_path, final_path))

for tmp_path, final_path in temp_img_map:
    os.rename(tmp_path, final_path)

print("✓ Renamed all image files in images/ to sequential 001.jpg -> 1446.jpg")

# 7. Two-pass rename for temp_audio/ if files exist
if os.path.exists("temp_audio"):
    temp_aud_map = []
    for old_idx, new_idx in mapping.items():
        old_file_3 = f"temp_audio/{old_idx:03d}.mp3"
        old_file_raw = f"temp_audio/{old_idx}.mp3"
        old_path = old_file_3 if os.path.exists(old_file_3) else old_file_raw
        
        tmp_path = f"temp_audio/__tmp_{new_idx:03d}.mp3"
        final_path = f"temp_audio/{new_idx:03d}.mp3"
        
        if os.path.exists(old_path):
            os.rename(old_path, tmp_path)
            temp_aud_map.append((tmp_path, final_path))

    for tmp_path, final_path in temp_aud_map:
        os.rename(tmp_path, final_path)
    print("✓ Renamed temp_audio files to sequential IDs.")

# 8. Rebuild cloudinary_videos.json with contiguous keys
new_cloud_data = {}
for old_idx, new_idx in mapping.items():
    # Key in old json might be str(old_idx) or f"{old_idx:03d}"
    old_key = str(old_idx) if str(old_idx) in cloud_data else f"{old_idx:03d}"
    if old_key in cloud_data:
        new_cloud_data[str(new_idx)] = cloud_data[old_key]
    else:
        print(f"Warning: old key {old_key} not in cloud_data!")

with open(PROGRESS_FILE, "w") as f:
    json.dump(new_cloud_data, f, indent=2)

print(f"✓ Rebuilt {PROGRESS_FILE} with {len(new_cloud_data)} contiguous records (1 to {len(new_cloud_data)}).")

# 9. Verification
new_videos = [f for f in os.listdir("videos") if f.endswith(".mp4")]
new_images = [f for f in os.listdir("images") if f.endswith(".jpg")]
new_cloud_keys = list(new_cloud_data.keys())

print("\n=======================================================")
print(f"VERIFICATION SUMMARY:")
print(f"  • Total Videos: {len(new_videos)} (Expected: 1446, 001.mp4 to 1446.mp4)")
print(f"  • Total Images: {len(new_images)} (Expected: 1446, 001.jpg to 1446.jpg)")
print(f"  • Total Cloudinary Records: {len(new_cloud_keys)} (Expected: 1446, 1 to 1446)")
print("=======================================================\n")
