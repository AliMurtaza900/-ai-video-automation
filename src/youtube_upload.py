import json
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def get_credentials():
    token = os.environ.get("YOUTUBE_TOKEN_JSON")
    if not token:
        raise RuntimeError(
            "YOUTUBE_TOKEN_JSON is not configured. Complete one-time YouTube OAuth setup first."
        )
    info = json.loads(token)
    creds = Credentials.from_authorized_user_info(info, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return creds


def main():
    video = OUTPUT / "final-video.mp4"
    if not video.exists():
        raise RuntimeError(f"Video not found: {video}")

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

    media = MediaFileUpload(str(video), mimetype="video/mp4", resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    print("Uploaded YouTube video:", response.get("id"))


if __name__ == "__main__":
    main()
