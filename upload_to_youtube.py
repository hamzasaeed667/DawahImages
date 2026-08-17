import socket
_old_gai = socket.getaddrinfo
def _ipv4_gai(host, port, family=0, type=0, proto=0, flags=0):
    return _old_gai(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = _ipv4_gai

import os
import sys
import json
import datetime
import requests
from dotenv import load_dotenv, set_key
from rank_youtube_videos import fetch_and_rank_videos

ENV_FILE = ".env"
PROGRESS_FILE = "upload_progress.json"
load_dotenv(ENV_FILE)

def clean_val(val):
    if not val:
        return ""
    return val.strip().strip("'").strip('"')

def get_access_token():
    client_id = clean_val(os.getenv("YOUTUBE_CLIENT_ID") or os.getenv("GOOGLE_ACCESS_TOKEN"))
    client_secret = clean_val(os.getenv("YOUTUBE_CLIENT_SECRET") or os.getenv("GOOGLE_ACCESS_SECRET"))
    refresh_token = clean_val(os.getenv("YOUTUBE_REFRESH_TOKEN") or os.getenv("GOOGLE_REFRESH_TOKEN"))

    if not (client_id and client_secret and refresh_token):
        print("Error: Missing YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, or YOUTUBE_REFRESH_TOKEN in .env", flush=True)
        sys.exit(1)

    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    }

    r = requests.post("https://oauth2.googleapis.com/token", data=data, timeout=15)
    if r.status_code == 200:
        token = r.json()["access_token"]
        set_key(ENV_FILE, "YOUTUBE_ACCESS_TOKEN", token)
        return token
    else:
        print(f"Error refreshing OAuth token: {r.status_code} - {r.text}", flush=True)
        sys.exit(1)

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_progress(progress):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)

def get_video_metadata(index):
    # Book categorization based on sequential numbering 1 to 1446
    if 1 <= index <= 455:
        book = "The Sublime Revelation (al-Fath ar-Rabbani)"
        title = f"The Sublime Revelation - Reminders (Part {index})"
        tags = ["Dawah", "Islam", "Spiritual", "Reminders", "Al-Fath ar-Rabbani", "Shaikh Abd al-Qadir al-Jilani"]
    elif 456 <= index <= 624:
        book = "Purification of the Mind (Jila' al-Khatir)"
        title = f"Purification of the Mind - Spiritual Wisdom (Part {index})"
        tags = ["Dawah", "Islam", "Spiritual", "Purification of Mind", "Jila al-Khatir", "Shaikh Abd al-Qadir al-Jilani"]
    elif 625 <= index <= 743:
        book = "Utterances of Shaikh 'Abd al-Qadir al-Jilani (Malfuzat)"
        title = f"Utterances of Shaikh Abd al-Qadir - Daily Wisdom (Part {index})"
        tags = ["Dawah", "Islam", "Spiritual", "Malfuzat", "Utterances", "Shaikh Abd al-Qadir al-Jilani"]
    elif 744 <= index <= 897:
        book = "Revelations of the Unseen (Futuh al-Ghaib)"
        title = f"Revelations of the Unseen - Discourse (Part {index})"
        tags = ["Dawah", "Islam", "Spiritual", "Futuh al-Ghaib", "Revelations of the Unseen", "Shaikh Abd al-Qadir al-Jilani"]
    else:
        book = "Necklaces of Gems (Qala'id al-Jawahir)"
        title = f"Necklaces of Gems - Biography & Virtues (Part {index})"
        tags = ["Dawah", "Islam", "Spiritual", "Necklaces of Gems", "Qalaid al-Jawahir", "Shaikh Abd al-Qadir al-Jilani"]

    description = (
        f"Daily spiritual reading from {book} "
        f"by Shaikh 'Abd al-Qadir al-Jilani.\n\n"
        f"Part {index} of 1446.\n\n"
        f"#Islam #Spiritual #Dawah #IslamicQuotes #ShaikhAbdAlQadirAlJilani"
    )

    return title, description, tags

def upload_video_file(access_token, video_path, title, description, tags, category_id="22", privacy_status="public"):
    file_size = os.path.getsize(video_path)

    # 1. Initiate Resumable Upload Session
    init_url = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
        "X-Upload-Content-Length": str(file_size),
        "X-Upload-Content-Type": "video/mp4"
    }
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category_id
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False
        }
    }

    resp = requests.post(init_url, headers=headers, json=body, timeout=30)
    if resp.status_code != 200:
        return None, resp.status_code, resp.text

    upload_url = resp.headers.get("Location")
    if not upload_url:
        return None, resp.status_code, "No Location header returned for upload session"

    # 2. Upload Video Binary Data
    upload_headers = {
        "Content-Type": "video/mp4",
        "Content-Length": str(file_size)
    }

    with open(video_path, "rb") as video_file:
        video_bytes = video_file.read()

    up_resp = requests.put(upload_url, headers=upload_headers, data=video_bytes, timeout=180)

    if up_resp.status_code in [200, 201]:
        video_id = up_resp.json().get("id")
        return video_id, up_resp.status_code, "OK"
    else:
        return None, up_resp.status_code, up_resp.text

def upload_next_batch():
    print("Authenticating with YouTube API...", flush=True)
    access_token = get_access_token()

    # Test connection & fetch channel info
    ch_resp = requests.get(
        "https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15
    ).json()

    if "items" in ch_resp and len(ch_resp["items"]) > 0:
        channel_title = ch_resp["items"][0]["snippet"]["title"]
        print(f"✓ Connected to YouTube Channel: {channel_title}\n", flush=True)
    else:
        print("Warning: Could not fetch channel title, proceeding with upload...\n", flush=True)

    progress = load_progress()

    # Find all videos on disk
    video_files = [f for f in os.listdir("videos") if f.endswith(".mp4")]
    video_nums = sorted([int(os.path.splitext(f)[0]) for f in video_files if os.path.splitext(f)[0].isdigit()])

    pending_videos = [n for n in video_nums if str(n) not in progress and f"{n:03d}" not in progress]

    print(f"=======================================================", flush=True)
    print(f"Starting Next Batch YouTube Upload ({len(pending_videos)} pending videos)", flush=True)
    print(f"=======================================================\n", flush=True)

    if not pending_videos:
        print("All videos have already been uploaded to YouTube!")
        fetch_and_rank_videos()
        return

    uploaded_count = 0

    for i in pending_videos:
        file_id = f"{i:03d}"
        video_path = f"videos/{file_id}.mp4"

        if not os.path.exists(video_path):
            video_path = f"videos/{i}.mp4"
            if not os.path.exists(video_path):
                print(f"[{file_id}] Skipping (Video file not found)", flush=True)
                continue

        title, description, tags = get_video_metadata(i)

        print(f"[{file_id}] Uploading: {title}...", flush=True)

        yt_id, status_code, err_msg = upload_video_file(
            access_token, video_path, title, description, tags
        )

        if yt_id:
            progress[str(i)] = {
                "youtube_id": yt_id,
                "title": title,
                "uploaded_at": datetime.datetime.utcnow().isoformat()
            }
            save_progress(progress)
            uploaded_count += 1
            print(f"  ✓ Uploaded! URL: https://youtu.be/{yt_id}", flush=True)
        else:
            print(f"  ❌ Upload failed with status {status_code}: {err_msg}", flush=True)
            if "quotaExceeded" in err_msg or status_code == 403:
                print(f"\n⚠️ YouTube API Quota or Upload Limit reached.", flush=True)
                print(f"Progress saved. Run this script again when limit resets!", flush=True)
                break
            elif "uploadLimitExceeded" in err_msg:
                print(f"\n⚠️ YouTube Channel Daily Upload Limit reached.", flush=True)
                print(f"Progress saved. Run this script again after 24h reset!", flush=True)
                break
            else:
                if status_code == 401:
                    print("Refreshing access token and retrying...", flush=True)
                    access_token = get_access_token()
                    yt_id, status_code, err_msg = upload_video_file(
                        access_token, video_path, title, description, tags
                    )
                    if yt_id:
                        progress[str(i)] = {
                            "youtube_id": yt_id,
                            "title": title,
                            "uploaded_at": datetime.datetime.utcnow().isoformat()
                        }
                        save_progress(progress)
                        uploaded_count += 1
                        print(f"  ✓ Uploaded after token refresh! URL: https://youtu.be/{yt_id}", flush=True)
                        continue
                print(f"Stopping batch due to error on video {file_id}.", flush=True)
                break

    print(f"\n=======================================================", flush=True)
    print(f"Batch Upload Session Complete: {uploaded_count} new videos uploaded.", flush=True)
    print(f"Total uploaded to YouTube: {len(progress)} / {len(video_nums)}", flush=True)
    print(f"=======================================================\n", flush=True)

    # Rank all videos after upload
    print("Updating video rankings...", flush=True)
    fetch_and_rank_videos()

if __name__ == "__main__":
    upload_next_batch()
