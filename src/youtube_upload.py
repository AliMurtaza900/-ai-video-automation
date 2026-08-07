import hashlib
import json
import os
import time
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
UPLOAD_RECORD = OUTPUT / "youtube_upload.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def get_credentials():
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN")
    client_id = os.environ.get("YOUTUBE_CLIENT_ID")
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")

    missing = [
        name for name, value in {
            "YOUTUBE_REFRESH_TOKEN": refresh_token,
            "YOUTUBE_CLIENT_ID": client_id,
            "YOUTUBE_CLIENT_SECRET": client_secret,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError("Missing GitHub secrets: " + ", ".join(missing))

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return creds


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    video = OUTPUT / "final-video.mp4"
    if not video.exists() or video.stat().st_size == 0:
        raise RuntimeError(f"Video not found or empty: {video}")

    video_hash = sha256_file(video)

    # A completed upload from this exact generated file is already known.
    # This protects against accidental duplicate execution of the same local artifact.
    if UPLOAD_RECORD.exists():
        try:
            record = json.loads(UPLOAD_RECORD.read_text(encoding="utf-8"))
            if record.get("sha256") == video_hash and record.get("youtube_id"):
                print("Upload already completed for this video:", record["youtube_id"])
                return
        except (OSError, json.JSONDecodeError):
            pass

    title = os.environ.get("YOUTUBE_TITLE", "Amazing AI Fact #shorts")[:100]
    description = os.environ.get(
        "YOUTUBE_DESCRIPTION",
        "An automatically generated interesting fact. #shorts #facts #ai",
    )

    youtube = build("youtube", "v3", credentials=get_credentials())
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": "27",
            "tags": ["shorts", "facts", "interesting facts", "AI"],
        },
        "status": {"privacyStatus": os.environ.get("YOUTUBE_PRIVACY", "private")},
    }

    # Resumable upload means transient network failures continue from the
    # current upload position instead of starting a brand-new YouTube upload.
    media = MediaFileUpload(
        str(video), mimetype="video/mp4", resumable=True, chunksize=8 * 1024 * 1024
    )
    request = youtube.videos().insert(
        part="snippet,status", body=body, media_body=media
    )

    response = None
    for attempt in range(1, 7):
        try:
            while response is None:
                _, response = request.next_chunk()
            break
        except HttpError as exc:
            if attempt == 6:
                raise
            # 5xx and rate-limit errors are normally transient. The same
            # resumable request object is reused so we don't intentionally
            # create a second upload.
            status = getattr(exc.resp, "status", None)
            if status not in {429, 500, 502, 503, 504}:
                raise
            delay = min(60, 5 * (2 ** (attempt - 1)))
            print(f"YouTube upload temporarily failed ({status}); retrying in {delay}s...")
            time.sleep(delay)
        except (OSError, ConnectionError) as exc:
            if attempt == 6:
                raise
            delay = min(60, 5 * (2 ** (attempt - 1)))
            print(f"YouTube connection failed; retrying in {delay}s: {exc}")
            time.sleep(delay)

    youtube_id = response.get("id") if response else None
    if not youtube_id:
        raise RuntimeError("YouTube upload returned no video ID")

    UPLOAD_RECORD.write_text(
        json.dumps(
            {"sha256": video_hash, "youtube_id": youtube_id, "title": title},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print("Uploaded YouTube video:", youtube_id)


if __name__ == "__main__":
    main()
