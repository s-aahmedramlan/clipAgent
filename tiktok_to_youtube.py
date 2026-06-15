#!/usr/bin/env python3
import csv
import os
import sys
from datetime import datetime
import yt_dlp
import anthropic
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
import googleapiclient.discovery
import googleapiclient.errors
import googleapiclient.http
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
YOUTUBE_CREDENTIALS_FILE = os.getenv("YOUTUBE_CREDENTIALS_FILE", "youtube_credentials.json")
CSV_FILE = os.getenv("CSV_FILE", "videos.csv")
VIDEOS_DIR = "downloaded_videos"

os.makedirs(VIDEOS_DIR, exist_ok=True)

def extract_caption_from_tiktok(tiktok_url: str) -> str | None:
    """Extract caption from TikTok metadata using yt-dlp."""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(tiktok_url, download=False)
            caption = info.get('description') or info.get('title') or ""
            return caption.strip() if caption else None
    except Exception as e:
        print(f"  ⚠ Could not extract caption from metadata: {e}")
        return None


def download_tiktok_video(tiktok_url: str, output_path: str) -> bool:
    """Download TikTok video without watermark using yt-dlp."""
    print(f"  Downloading from {tiktok_url}...")

    try:
        ydl_opts = {
            'outtmpl': output_path.replace('.mp4', ''),
            'quiet': False,
            'no_warnings': True,
            'format': 'best[vcodec!=h265]',
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([tiktok_url])

        print(f"  ✓ Downloaded to {output_path}")
        return True
    except Exception as e:
        print(f"  ✗ Download failed: {e}")
        return False


def rewrite_caption(original_caption: str) -> str:
    """Rewrite caption using Anthropic API, keeping keywords."""
    print(f"  Rewriting caption: '{original_caption[:50]}...'")

    client = anthropic.Anthropic()

    message = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": f"""Rewrite this caption for a YouTube Short to be slightly different but keep the same keywords and meaning. Keep it concise (under 150 chars). Only provide the new caption, nothing else.

Original caption: {original_caption}"""
            }
        ]
    )

    new_caption = message.content[0].text.strip()
    print(f"  ✓ New caption: '{new_caption}'")
    return new_caption


def get_youtube_service():
    """Authenticate with YouTube API."""
    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

    creds = None

    if os.path.exists("token.json"):
        from google.auth import load_credentials_from_file
        creds, _ = load_credentials_from_file("token.json")

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                YOUTUBE_CREDENTIALS_FILE, SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open("token.json", "w") as token:
            token.write(creds.to_json())

    return googleapiclient.discovery.build("youtube", "v3", credentials=creds)


def upload_to_youtube(video_path: str, caption: str, title: str = None) -> str | None:
    """Upload video to YouTube Shorts."""
    if title is None:
        title = caption[:50]

    print(f"  Uploading to YouTube with title: '{title}'")

    try:
        youtube = get_youtube_service()

        body = {
            "snippet": {
                "title": title,
                "description": caption,
                "tags": ["shorts"],
                "categoryId": "22",
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False,
            }
        }

        with open(video_path, "rb") as f:
            request = youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=googleapiclient.http.MediaFileUpload(
                    video_path,
                    mimetype="video/mp4"
                )
            )
            response = request.execute()

        video_id = response.get("id")
        print(f"  ✓ Uploaded with ID: {video_id}")
        return video_id
    except Exception as e:
        print(f"  ✗ Upload failed: {e}")
        return None


def process_csv():
    """Read CSV, process videos, update status."""
    if not os.path.exists(CSV_FILE):
        print(f"Error: {CSV_FILE} not found")
        sys.exit(1)

    rows = []
    with open(CSV_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    for i, row in enumerate(rows):
        if row.get("status") == "done":
            print(f"[{i+1}/{len(rows)}] Skipping (already done): {row.get('tiktok_url', 'N/A')[:40]}")
            continue

        tiktok_url = (row.get("tiktok_url") or "").strip()
        caption = (row.get("caption") or "").strip()

        if not tiktok_url:
            print(f"[{i+1}/{len(rows)}] Skipping (missing URL)")
            row["status"] = "error"
            row["error"] = "Missing URL"
            continue

        if not caption:
            print(f"  Extracting caption from video metadata...")
            caption = extract_caption_from_tiktok(tiktok_url)
            if not caption:
                print(f"[{i+1}/{len(rows)}] Skipping (no caption found)")
                row["status"] = "error"
                row["error"] = "No caption found in video"
                continue

        print(f"\n[{i+1}/{len(rows)}] Processing: {tiktok_url[:50]}...")

        video_filename = f"{VIDEOS_DIR}/video_{i}_{int(datetime.now().timestamp())}.mp4"

        if not download_tiktok_video(tiktok_url, video_filename):
            row["status"] = "error"
            row["error"] = "Download failed"
            continue

        new_caption = rewrite_caption(caption)

        youtube_id = upload_to_youtube(video_filename, new_caption)
        if not youtube_id:
            row["status"] = "error"
            row["error"] = "Upload failed"
            continue

        row["status"] = "done"
        row["youtube_id"] = youtube_id
        row["new_caption"] = new_caption
        row["processed_at"] = datetime.now().isoformat()

        try:
            os.remove(video_filename)
        except:
            pass

    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        if rows:
            fieldnames = list(rows[0].keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    print("\n✓ CSV updated with results")


if __name__ == "__main__":
    process_csv()
