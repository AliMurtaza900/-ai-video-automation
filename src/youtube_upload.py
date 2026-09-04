import hashlib
import json
import os
import time
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from create_thumbnail import create as create_thumbnail

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
UPLOAD_RECORD = OUTPUT / "youtube_upload.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_URI = "https://oauth2.googleapis.com/token"


def get_credentials():
    """Build YouTube credentials from the long-lived refresh-token secret.

    GitHub Actions should persist only the refresh token as a secret. Google
    access tokens are intentionally short-lived and are refreshed on demand
    by google-auth; they must never be committed to the repository.
    """
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN")
    client_id = os.environ.get("YOUTUBE_CLIENT_ID")
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")
    missing = [
        name
        for name, value in {
            "YOUTUBE_REFRESH_TOKEN": refresh_token,
            "YOUTUBE_CLIENT_ID": client_id,
            "YOUTUBE_CLIENT_SECRET": client_secret,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError("Missing GitHub secrets: " + ", ".join(missing))

    # Do not persist or cache the short-lived access token. Reconstruct the
    # credential from the persistent refresh token on every workflow run.
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=TOKEN_URI,
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )

    try:
        # This obtains a fresh access token using the persistent refresh token.
        # Subsequent API requests can refresh it again automatically if needed.
        creds.refresh(Request())
    except RefreshError as exc:
        detail = str(exc)
        if "invalid_grant" in detail.lower():
            raise RuntimeError(
                "YouTube refresh token was rejected by Google (invalid_grant). "
                "Re-authorize the YouTube OAuth app with offline access and replace "
                "the GitHub YOUTUBE_REFRESH_TOKEN secret. If the Google OAuth app "
                "is still in Testing mode, move it to Production to avoid the "
                "short testing-mode refresh-token lifetime."
            ) from exc
        raise RuntimeError(
            "YouTube OAuth token refresh failed. Check YOUTUBE_CLIENT_ID, "
            "YOUTUBE_CLIENT_SECRET, and YOUTUBE_REFRESH_TOKEN."
        ) from exc

    if not creds.valid or not creds.token:
        raise RuntimeError("Google returned an invalid YouTube access token after refresh")

    return creds


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def set_thumbnail(youtube, video_id, thumbnail):
    for attempt in range(1, 6):
        try:
            youtube.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(thumbnail), mimetype="image/jpeg")).execute()
            print(f"Thumbnail set for YouTube video: {video_id}")
            return True
        except HttpError as exc:
            status = getattr(exc.resp, "status", None)
            if status == 403:
                print("WARNING: YouTube rejected the custom thumbnail (403 permission). Video upload remains successful.")
                return False
            if status not in {429, 500, 502, 503, 504} or attempt == 5:
                print(f"WARNING: Could not set thumbnail after {attempt} attempts: {exc}")
                return False
            delay = min(60, 5 * (2 ** (attempt - 1)))
            print(f"Thumbnail API temporarily failed ({status}); retrying in {delay}s...")
            time.sleep(delay)
        except Exception as exc:
            print(f"WARNING: Thumbnail operation failed: {exc}")
            return False
    return False


def derive_title_from_script() -> str:
    """Best-effort title from the generated narration when none is supplied."""
    script_path = OUTPUT / "script.txt"
    if not script_path.exists():
        return "Surprising Fact You Need to Know"
    text = script_path.read_text(encoding="utf-8").strip()
    if not text:
        return "Surprising Fact You Need to Know"
    # Take the first sentence and keep it under ~70 chars for Shorts.
    first = text.split(".")[0].strip()
    if len(first) > 70:
        first = first[:67].rsplit(" ", 1)[0] + "..."
    return first or "Surprising Fact You Need to Know"


def main():
    video = OUTPUT / "final-video.mp4"
    if not video.exists() or video.stat().st_size == 0:
        raise RuntimeError(f"Video not found or empty: {video}")

    video_hash = sha256_file(video)
    title = os.environ.get("YOUTUBE_TITLE") or derive_title_from_script()
    title = title[:100]
    description = os.environ.get(
        "YOUTUBE_DESCRIPTION",
        "A short, surprising fact narrated and edited automatically for YouTube Shorts. "
        "Educational / entertainment content suitable for general audiences.",
    )
    made_for_kids = os.environ.get("YOUTUBE_MADE_FOR_KIDS", "false").lower() in ("1", "true", "yes")
    category_id = os.environ.get("YOUTUBE_CATEGORY_ID", "27")  # 27 = Education (good default for facts)

    youtube = build("youtube", "v3", credentials=get_credentials())
    thumbnail = create_thumbnail(video, title)

    if UPLOAD_RECORD.exists():
        try:
            record = json.loads(UPLOAD_RECORD.read_text(encoding="utf-8"))
            if record.get("sha256") == video_hash and record.get("youtube_id"):
                set_thumbnail(youtube, record["youtube_id"], thumbnail)
                print("Upload already completed for this video:", record["youtube_id"])
                return
        except (OSError, json.JSONDecodeError):
            pass

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": category_id,
            "tags": [
                "facts",
                "did you know",
                "surprising facts",
                "youtube shorts",
                "education",
                "interesting facts",
                "science",
                "history",
            ],
        },
        "status": {
            "privacyStatus": os.environ.get("YOUTUBE_PRIVACY", "private"),
            "selfDeclaredMadeForKids": made_for_kids,
        },
    }
    media = MediaFileUpload(str(video), mimetype="video/mp4", resumable=True, chunksize=8 * 1024 * 1024)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    for attempt in range(1, 7):
        try:
            while response is None:
                _, response = request.next_chunk()
            break
        except HttpError as exc:
            if attempt == 6:
                raise
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
        json.dumps({"sha256": video_hash, "youtube_id": youtube_id, "title": title}, indent=2) + "\n",
        encoding="utf-8",
    )
    set_thumbnail(youtube, youtube_id, thumbnail)
    print("Uploaded YouTube video:", youtube_id)


if __name__ == "__main__":
    main()
