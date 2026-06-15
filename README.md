# TikTok to YouTube Shorts Automation

Converts TikTok videos to YouTube Shorts with rewritten captions using Claude.

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Get API credentials

**Anthropic API:**
- Sign up at https://console.anthropic.com
- Create an API key

**YouTube API:**
- Go to https://console.cloud.google.com
- Create a new project
- Enable YouTube Data API v3
- Create OAuth 2.0 credentials (Desktop app)
- Download the JSON file as `youtube_credentials.json`

### 3. Configure environment
```bash
cp .env.example .env
```

Edit `.env` and add your credentials:
- `ANTHROPIC_API_KEY`: Your Claude API key
- `YOUTUBE_CREDENTIALS_FILE`: Path to YouTube credentials JSON
- `CSV_FILE`: Path to your videos CSV

### 4. Prepare your CSV
Create `videos.csv` with columns:
- `tiktok_url`: Full TikTok video URL
- `caption`: Original caption
- `status`: Leave empty for new videos
- Other columns are auto-populated

Example:
```csv
tiktok_url,caption,status,youtube_id,new_caption,processed_at,error
https://www.tiktok.com/@user/video/123,Cool hack for productivity,
https://www.tiktok.com/@user/video/456,Life changing tip,
```

## Usage

```bash
python tiktok_to_youtube.py
```

The script will:
1. Read each row in `videos.csv`
2. Skip videos already marked as `done`
3. Download the video without watermark
4. Rewrite the caption using Claude
5. Upload to YouTube as a Short
6. Mark the row as `done` and save the YouTube ID
7. Clean up the downloaded video file

On error, the row is marked with `status=error` and error details.

## Notes

- First run will open a browser to authorize YouTube access
- YouTube auth token is saved to `token.json`
- Downloaded videos are temporarily stored in `downloaded_videos/`
- All updates are saved back to the CSV after processing
- Re-running the script will skip already-processed videos

## Cost considerations

- yt-dlp is completely free (open source)
- Anthropic API charges per token (~$0.01 per video for caption rewrite)
- YouTube uploads are free but limited to quota per day (default 6 hours)
