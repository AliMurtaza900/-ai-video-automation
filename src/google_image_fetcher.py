from __future__ import annotations

"""Fetch visual assets discovered through Google Images without a paid API.

This module is deliberately isolated from the renderer. It downloads only the
image URLs exposed by Google's public image-search result page, caches them,
and validates the downloaded bytes. The renderer can fall back to its built-in
art whenever Google changes the result markup or a source blocks downloading.

Use this for scenes where the topic benefits from real-world visual grounding.
For publishable videos, callers should prefer assets whose source/license
permits reuse; Google Images itself is a discovery index, not a license grant.
"""

import hashlib
import html
import re
import ssl
import time
from pathlib import Path
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "output" / "kids_animation" / "google_images"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36"

_URL_RE = re.compile(r'https?://[^\"\\ ]+')


def _clean_url(value: str) -> str:
    value = html.unescape(value).replace('\\u003d', '=').replace('\\u0026', '&')
    value = value.replace('\\/', '/')
    return value.strip('"\' ,;')


def search_google_images(query: str, limit: int = 8) -> list[str]:
    """Return candidate image URLs from a Google Images HTML result page."""
    if not query.strip():
        return []
    url = "https://www.google.com/search?tbm=isch&safe=active&q=" + quote(query.strip())
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"})
    ctx = ssl.create_default_context()
    with urlopen(req, timeout=20, context=ctx) as response:
        text = response.read().decode("utf-8", errors="ignore")

    candidates: list[str] = []
    seen: set[str] = set()
    for raw in _URL_RE.findall(text):
        candidate = _clean_url(raw)
        parsed = urlparse(candidate)
        if parsed.scheme not in {"http", "https"}:
            continue
        if "gstatic.com" in parsed.netloc or "google.com" in parsed.netloc:
            continue
        if candidate in seen:
            continue
        # Prefer URLs that look like actual image resources rather than search pages.
        if any(ext in parsed.path.lower() for ext in (".jpg", ".jpeg", ".png", ".webp")):
            seen.add(candidate)
            candidates.append(candidate)
        if len(candidates) >= limit:
            break
    return candidates


def download_image(url: str, destination: Path) -> bool:
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8"})
        with urlopen(req, timeout=20) as response:
            data = response.read(8 * 1024 * 1024 + 1)
        if len(data) < 10 or len(data) > 8 * 1024 * 1024:
            return False
        if not data.startswith((b"\xff\xd8\xff", b"\x89PNG", b"RIFF")):
            return False
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        return True
    except Exception:
        return False


def fetch_scene_image(query: str, scene_number: int) -> Path | None:
    """Download/cache one Google image for a scene, trying several candidates."""
    CACHE.mkdir(parents=True, exist_ok=True)
    target = CACHE / f"scene_{scene_number:03d}.img"
    if target.exists() and target.stat().st_size > 1000:
        return target
    try:
        candidates = search_google_images(query, limit=8)
    except Exception:
        return None
    for candidate in candidates:
        suffix = Path(urlparse(candidate).path).suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
            suffix = ".img"
        temporary = CACHE / (hashlib.sha256(candidate.encode()).hexdigest()[:16] + suffix)
        if download_image(candidate, temporary):
            # Keep a stable scene filename while retaining the source-specific cache.
            target.write_bytes(temporary.read_bytes())
            time.sleep(0.15)
            return target
    return None


def build_scene_queries(topic: str, scenes: list[tuple[str, str]]) -> list[str]:
    base = topic.strip() or "children story"
    return [f"{base} {kind} {action} beautiful child friendly illustration" for kind, action in scenes]


if __name__ == "__main__":
    import os
    topic = os.getenv("TOPIC", "Milo and the Little Flower")
    print("Google Images visual discovery:", topic)
