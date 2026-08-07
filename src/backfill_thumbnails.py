import io
import os
import time
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
THUMBNAILS = OUTPUT / "backfill_thumbnails"
THUMBNAILS.mkdir(parents=True, exist_ok=True)
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
W, H = 1280, 720


def font(size):
    path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    return ImageFont.truetype(path, size) if Path(path).exists() else ImageFont.load_default()


def credentials():
    values = {k: os.environ.get(k) for k in ("YOUTUBE_REFRESH_TOKEN", "YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET")}
    missing = [k for k, v in values.items() if not v]
    if missing:
        raise RuntimeError("Missing GitHub secrets: " + ", ".join(missing))
    c = Credentials(token=None, refresh_token=values["YOUTUBE_REFRESH_TOKEN"], token_uri="https://oauth2.googleapis.com/token", client_id=values["YOUTUBE_CLIENT_ID"], client_secret=values["YOUTUBE_CLIENT_SECRET"], scopes=SCOPES)
    c.refresh(Request())
    return c


def make_thumbnail(source_url, title, path):
    response = requests.get(source_url, timeout=30)
    response.raise_for_status()
    image = Image.open(io.BytesIO(response.content)).convert("RGB").resize((W, H))
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for y in range(H):
        alpha = int(175 * max(0, 1 - y / H))
        draw.line((0, y, W, y), fill=(0, 0, 0, alpha))
    draw.rounded_rectangle((48, 48, 310, 112), radius=18, fill=(220, 38, 38, 235))
    draw.text((78, 62), "DID YOU KNOW?", font=font(28), fill="white")

    words = " ".join(title.split())[:72].split()
    lines, current = [], ""
    f = font(58)
    for word in words:
        test = f"{current} {word}".strip()
        if draw.textbbox((0, 0), test, font=f)[2] <= 1120:
            current = test
        else:
            if current: lines.append(current)
            current = word
        if len(lines) >= 2: break
    if current and len(lines) < 3: lines.append(current)
    y = 410 - (len(lines) - 1) * 34
    for line in lines[:3]:
        box = draw.textbbox((0, 0), line, font=f, stroke_width=4)
        x = (W - (box[2] - box[0])) // 2
        draw.text((x, y), line, font=f, fill="white", stroke_width=5, stroke_fill=(0, 0, 0, 220))
        y += 72
    final = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    final.save(path, "JPEG", quality=94, optimize=True)


def set_thumbnail(youtube, video_id, path):
    for attempt in range(5):
        try:
            youtube.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(path), mimetype="image/jpeg")).execute()
            return True
        except HttpError as exc:
            status = getattr(exc.resp, "status", None)
            if status not in {429, 500, 502, 503, 504} or attempt == 4:
                print(f"Thumbnail failed for {video_id}: {exc}")
                return False
            time.sleep(min(60, 5 * (2 ** attempt)))


def main():
    youtube = build("youtube", "v3", credentials=credentials())
    channel = youtube.channels().list(part="contentDetails", mine=True).execute()["items"][0]
    uploads_playlist = channel["contentDetails"]["relatedPlaylists"]["uploads"]
    response = youtube.playlistItems().list(part="snippet,contentDetails", playlistId=uploads_playlist, maxResults=20).execute()
    items = response.get("items", [])
    print(f"Backfilling thumbnails for {len(items)} recent videos")
    changed = 0
    for item in items:
        video_id = item["contentDetails"]["videoId"]
        snippet = item["snippet"]
        title = snippet.get("title", "Amazing Fact")
        thumbs = snippet.get("thumbnails", {})
        source = (thumbs.get("high") or thumbs.get("medium") or thumbs.get("default") or {}).get("url")
        if not source:
            print(f"Skipping {video_id}: no source thumbnail")
            continue
        path = THUMBNAILS / f"{video_id}.jpg"
        try:
            make_thumbnail(source, title, path)
            if set_thumbnail(youtube, video_id, path):
                changed += 1
                print(f"Updated thumbnail: {video_id} — {title}")
        except Exception as exc:
            print(f"Skipping {video_id}: {exc}")
    print(f"THUMBNAIL_BACKFILL updated={changed} total={len(items)}")


if __name__ == "__main__":
    main()
