import os
import sys
import json
import datetime
import socket
socket.setdefaulttimeout(120)
from dotenv import load_dotenv, set_key
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

ENV_FILE = ".env"
PROGRESS_FILE = "upload_progress.json"
load_dotenv(ENV_FILE)

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube"]

def clean_val(val):
    if not val:
        return ""
    return val.strip().strip("'").strip('"')

def get_authenticated_service():
    client_id = clean_val(os.getenv("YOUTUBE_CLIENT_ID") or os.getenv("GOOGLE_ACCESS_TOKEN"))
    client_secret = clean_val(os.getenv("YOUTUBE_CLIENT_SECRET") or os.getenv("GOOGLE_ACCESS_SECRET"))
    refresh_token = clean_val(os.getenv("YOUTUBE_REFRESH_TOKEN") or os.getenv("GOOGLE_REFRESH_TOKEN"))
    access_token = clean_val(os.getenv("YOUTUBE_ACCESS_TOKEN"))

    creds = None

    if client_id and client_secret and refresh_token:
        creds = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=SCOPES
        )

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        set_key(ENV_FILE, "YOUTUBE_ACCESS_TOKEN", creds.token)

    if not creds or not creds.valid:
        if client_id and client_secret:
            client_config = {
                "installed": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["http://localhost:8080/"]
                }
            }
            flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
        elif os.path.exists("client_secret.json"):
            flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
        else:
            print("Error: Neither .env credentials nor client_secret.json found.")
            sys.exit(1)

        creds = flow.run_local_server(port=8080)

        set_key(ENV_FILE, "YOUTUBE_CLIENT_ID", creds.client_id)
        set_key(ENV_FILE, "YOUTUBE_CLIENT_SECRET", creds.client_secret)
        set_key(ENV_FILE, "YOUTUBE_REFRESH_TOKEN", creds.refresh_token)
        set_key(ENV_FILE, "YOUTUBE_ACCESS_TOKEN", creds.token)
        print("✓ Tokens saved successfully to .env!")

    return build("youtube", "v3", credentials=creds)

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_progress(progress):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)

def upload_and_schedule_videos(start_date=None, start_index=1, end_index=455):
    youtube = get_authenticated_service()
    
    # Test connection
    channel_resp = youtube.channels().list(part="snippet", mine=True).execute()
    channel_title = channel_resp['items'][0]['snippet']['title']
    print(f"Connected to YouTube Channel: {channel_title}")

    progress = load_progress()

    if start_date is None:
        start_date = datetime.datetime.utcnow() + datetime.timedelta(days=1)
        start_date = start_date.replace(hour=9, minute=0, second=0, microsecond=0)

    print(f"\n=======================================================")
    print(f"Starting Batch Upload & Daily Scheduling (001 to 455)")
    print(f"First video scheduled date: {start_date.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"=======================================================\n")

    uploaded_count = 0

    for i in range(start_index, end_index + 1):
        file_id = f"{i:03d}"
        video_path = f"videos/{file_id}.mp4"

        if file_id in progress:
            print(f"[{file_id}] Already uploaded: https://youtu.be/{progress[file_id]['youtube_id']} (Scheduled for {progress[file_id]['scheduled_date']})")
            continue

        if not os.path.exists(video_path):
            print(f"[{file_id}] Warning: Video file missing: {video_path}")
            continue

        publish_time = start_date + datetime.timedelta(days=(i - start_index))
        publish_iso = publish_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        title = f"The Sublime Revelation - Reminders (Part {i})"
        description = (
            f"Daily spiritual reading from The Sublime Revelation (al-Fath ar-Rabbani) "
            f"by Shaikh 'Abd al-Qadir al-Jilani.\n\n"
            f"Part {i} of 455."
        )

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": ["Dawah", "Islam", "Spiritual", "Reminders", "Al-Fath ar-Rabbani"],
                "categoryId": "22"
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False
            }
        }

        print(f"[{file_id}] Uploading {video_path} ➔ Public Visibility...")


        try:
            media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
            request = youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media
            )

            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    print(f"  Progress: {int(status.progress() * 100)}%", end="\r")

            yt_id = response.get("id")
            progress[file_id] = {
                "youtube_id": yt_id,
                "scheduled_date": publish_iso,
                "uploaded_at": datetime.datetime.utcnow().isoformat()
            }
            save_progress(progress)
            uploaded_count += 1
            print(f"  ✓ Uploaded! URL: https://youtu.be/{yt_id}")

        except HttpError as e:
            err_str = str(e)
            if "quotaExceeded" in err_str:
                print(f"\n⚠️ YouTube API Daily Quota Limit Reached for today.")
                print(f"Progress saved. Run this script again tomorrow to resume automatically!")
                break
            elif "uploadLimitExceeded" in err_str:
                print(f"\n⚠️ YouTube Channel Daily Upload Limit Reached for today.")
                print(f"YouTube limits the number of videos a channel can upload per 24-hour window.")
                print(f"Progress saved. Try running this script again after the 24-hour window resets!")
                break
            else:
                print(f"[{file_id}] HttpError: {e}")
                break
        except Exception as e:
            print(f"[{file_id}] Error: {e}")
            break

    print(f"\n=======================================================")
    print(f"Batch Upload Completed: {uploaded_count} videos uploaded today.")
    print(f"Total uploaded so far: {len(progress)} / 455")
    print(f"=======================================================")

if __name__ == "__main__":
    upload_and_schedule_videos()
