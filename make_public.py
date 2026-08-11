import os
import json
from dotenv import load_dotenv, set_key
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

ENV_FILE = ".env"
PROGRESS_FILE = "upload_progress.json"
load_dotenv(ENV_FILE)

def clean_val(val):
    return val.strip().strip("'").strip('"') if val else ''

def get_authenticated_service():
    client_id = clean_val(os.getenv("YOUTUBE_CLIENT_ID") or os.getenv("GOOGLE_ACCESS_TOKEN"))
    client_secret = clean_val(os.getenv("YOUTUBE_CLIENT_SECRET") or os.getenv("GOOGLE_ACCESS_SECRET"))
    refresh_token = clean_val(os.getenv("YOUTUBE_REFRESH_TOKEN") or os.getenv("GOOGLE_REFRESH_TOKEN"))
    access_token = clean_val(os.getenv("YOUTUBE_ACCESS_TOKEN"))

    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube"]
    )

    if creds and creds.expired and creds.refresh_token:
        from google.auth.transport.requests import Request
        creds.refresh(Request())
        set_key(ENV_FILE, "YOUTUBE_ACCESS_TOKEN", creds.token)

    return build("youtube", "v3", credentials=creds)

def make_all_videos_public():
    if not os.path.exists(PROGRESS_FILE):
        print(f"No {PROGRESS_FILE} found.")
        return

    with open(PROGRESS_FILE, "r") as f:
        progress = json.load(f)

    if not progress:
        print("No uploaded videos found in progress file.")
        return

    youtube = get_authenticated_service()
    print(f"Updating {len(progress)} videos to PUBLIC status...\n")

    for file_id, info in progress.items():
        yt_id = info["youtube_id"]
        try:
            # Fetch snippet for title preservation
            res = youtube.videos().list(part="snippet,status", id=yt_id).execute()
            if not res["items"]:
                print(f"[{file_id}] Video {yt_id} not found on YouTube.")
                continue

            item = res["items"][0]
            snippet = item["snippet"]

            # Update status to public
            youtube.videos().update(
                part="snippet,status",
                body={
                    "id": yt_id,
                    "snippet": snippet,
                    "status": {
                        "privacyStatus": "public",
                        "selfDeclaredMadeForKids": False
                    }
                }
            ).execute()

            print(f"✓ [{file_id}] Video {yt_id} is now PUBLIC! ➔ https://youtu.be/{yt_id}")

        except Exception as e:
            print(f"[{file_id}] Error updating {yt_id}: {e}")

if __name__ == "__main__":
    make_all_videos_public()
