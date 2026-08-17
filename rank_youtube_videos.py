import socket
_old_gai = socket.getaddrinfo
def _ipv4_gai(host, port, family=0, type=0, proto=0, flags=0):
    return _old_gai(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = _ipv4_gai

import os
import json
import requests
from dotenv import load_dotenv

def clean_val(val):
    if not val:
        return ""
    return val.strip().strip("'").strip('"')

def get_access_token():
    load_dotenv(".env")
    client_id = clean_val(os.getenv("YOUTUBE_CLIENT_ID"))
    client_secret = clean_val(os.getenv("YOUTUBE_CLIENT_SECRET"))
    refresh_token = clean_val(os.getenv("YOUTUBE_REFRESH_TOKEN"))

    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    }

    r = requests.post("https://oauth2.googleapis.com/token", data=data, timeout=10)
    if r.status_code == 200:
        return r.json()["access_token"]
    else:
        raise Exception(f"Failed to refresh token: {r.text}")

def fetch_and_rank_videos():
    if not os.path.exists("upload_progress.json"):
        print("No upload_progress.json file found.", flush=True)
        return []

    with open("upload_progress.json", "r") as f:
        progress = json.load(f)

    if not progress:
        print("No uploaded videos found in upload_progress.json", flush=True)
        return []

    print("Refreshing OAuth access token...", flush=True)
    access_token = get_access_token()
    headers = {"Authorization": f"Bearer {access_token}"}

    # Map youtube_id to part/file_id
    yt_map = {v["youtube_id"]: file_id for file_id, v in progress.items() if "youtube_id" in v}
    video_ids = list(yt_map.keys())
    print(f"Fetching analytics for {len(video_ids)} uploaded videos via YouTube API...", flush=True)

    all_stats = []

    # Batch in chunks of 50
    chunk_size = 50
    for i in range(0, len(video_ids), chunk_size):
        chunk = video_ids[i:i+chunk_size]
        url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics&id={','.join(chunk)}"
        resp = requests.get(url, headers=headers, timeout=10).json()

        for item in resp.get("items", []):
            yt_id = item["id"]
            file_id = yt_map.get(yt_id, "Unknown")
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})

            views = int(stats.get("viewCount", 0))
            likes = int(stats.get("likeCount", 0))
            comments = int(stats.get("commentCount", 0))
            title = snippet.get("title", f"Part {file_id}")
            published_at = snippet.get("publishedAt", "")

            all_stats.append({
                "file_id": file_id,
                "youtube_id": yt_id,
                "title": title,
                "views": views,
                "likes": likes,
                "comments": comments,
                "published_at": published_at,
                "url": f"https://youtu.be/{yt_id}"
            })

    # Sort by views descending, then likes descending, then comments descending
    all_stats.sort(key=lambda x: (x["views"], x["likes"], x["comments"]), reverse=True)

    print("\n=======================================================", flush=True)
    print(f"📊 YOUTUBE VIDEO RANKINGS ({len(all_stats)} Uploaded Videos)", flush=True)
    print("=======================================================\n", flush=True)

    for rank, vid in enumerate(all_stats, 1):
        print(f"#{rank:02d} | Part {vid['file_id']} | Views: {vid['views']} | Likes: {vid['likes']} | Comments: {vid['comments']} | Title: {vid['title']}", flush=True)

    with open("youtube_rankings.json", "w") as f:
        json.dump(all_stats, f, indent=2)

    # Save Markdown report
    md_lines = [
        "# 📊 YouTube Video Performance Rankings",
        f"**Total Videos Analyzed**: {len(all_stats)}\n",
        "| Rank | Part | Title | Views | Likes | Comments | YouTube Link |",
        "| --- | --- | --- | --- | --- | --- | --- |"
    ]
    for rank, vid in enumerate(all_stats, 1):
        md_lines.append(f"| #{rank} | Part {vid['file_id']} | {vid['title']} | **{vid['views']}** | {vid['likes']} | {vid['comments']} | [Watch Video]({vid['url']}) |")

    with open("YOUTUBE_RANKINGS.md", "w") as f:
        f.write("\n".join(md_lines))

    print("\n✓ Saved rankings to youtube_rankings.json and YOUTUBE_RANKINGS.md", flush=True)
    return all_stats

if __name__ == "__main__":
    fetch_and_rank_videos()
