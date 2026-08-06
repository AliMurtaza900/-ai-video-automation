import html
import re
from pathlib import Path
from urllib.parse import quote
import requests

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
ASSETS = ROOT / "assets"
VISUALS = ASSETS / "visuals"
VISUALS.mkdir(parents=True, exist_ok=True)

API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "AI-Video-Automation/1.1 (educational video project)"}
VIDEO_MIMES = {"video/mp4", "video/webm", "video/ogg"}
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")

STOP = {
    "about", "after", "again", "because", "before", "could", "every", "first",
    "from", "have", "into", "more", "most", "never", "only", "other", "over",
    "really", "their", "there", "these", "this", "those", "through", "what",
    "when", "where", "which", "while", "with", "would", "your", "that", "than",
    "they", "them", "then", "were", "will", "also", "some", "many", "fact",
    "facts", "interesting", "people", "thing", "story", "stories", "history",
}


def clean(value):
    return re.sub(r"\s+", " ", html.unescape(re.sub("<.*?>", " ", value or ""))).strip()


def keywords(script):
    words = re.findall(r"[A-Za-z]{4,}", script.lower())
    result = []
    for word in words:
        if word not in STOP and word not in result:
            result.append(word)
        if len(result) >= 12:
            break
    return result


def search_media(term, video=True):
    query = f"{term} filetype:video" if video else term
    params = {
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": query, "gsrnamespace": 6, "gsrlimit": 15,
        "prop": "imageinfo|info", "iiprop": "url|mime|size|extmetadata",
        "inprop": "url",
    }
    response = requests.get(API, params=params, timeout=20, headers=UA)
    response.raise_for_status()
    pages = response.json().get("query", {}).get("pages", {})
    candidates = []
    for page in pages.values():
        info = page.get("imageinfo", [{}])[0]
        url = info.get("url")
        mime = info.get("mime", "")
        if not url:
            continue
        meta = info.get("extmetadata", {})
        title = clean(meta.get("ObjectName", {}).get("value", page.get("title", term)))
        artist = clean(meta.get("Artist", {}).get("value", ""))
        license_name = clean(meta.get("LicenseShortName", {}).get("value", ""))
        description = clean(meta.get("ImageDescription", {}).get("value", ""))
        candidates.append({
            "url": url, "mime": mime, "title": title,
            "artist": artist, "license": license_name,
            "description": description,
            "pageid": page.get("pageid", ""),
            "pageurl": page.get("fullurl", f"https://commons.wikimedia.org/wiki/{quote(page.get('title',''))}"),
        })

    if video:
        candidates = [c for c in candidates if c["mime"] in VIDEO_MIMES]
    else:
        candidates = [c for c in candidates if c["url"].lower().split("?")[0].endswith(IMAGE_EXTS)]
    return candidates


def relevance(candidate, terms):
    text = f"{candidate['title']} {candidate['description']}".lower()
    score = sum(3 if t in candidate["title"].lower() else 1 for t in terms if t in text)
    if candidate["license"]:
        score += 2
    if candidate["mime"] in VIDEO_MIMES:
        score += 3
    return score


def download(candidate, index):
    response = requests.get(candidate["url"], timeout=120, headers=UA, stream=True)
    response.raise_for_status()
    suffix = ".webm" if candidate["mime"] == "video/webm" else ".mp4" if candidate["mime"] == "video/mp4" else ".jpg"
    path = VISUALS / f"visual_{index:02d}{suffix}"
    size = 0
    with path.open("wb") as f:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)
                size += len(chunk)
                if size > 150 * 1024 * 1024:
                    raise RuntimeError("media file exceeds 150 MB safety limit")
    if size < 50_000:
        path.unlink(missing_ok=True)
        raise RuntimeError("media file is unexpectedly small")
    return path


def main():
    script = (OUTPUT / "script.txt").read_text(encoding="utf-8").strip()
    if not script:
        raise RuntimeError("Generated script is empty")

    for old in VISUALS.glob("visual_*"):
        old.unlink()
    for old in VISUALS.glob("*.txt"):
        old.unlink()

    terms = keywords(script)
    print("Visual search terms:", ", ".join(terms))

    selected = []
    used_urls = set()
    # Search each meaningful concept separately so one generic result doesn't
    # dominate the whole video.
    for term in terms:
        try:
            candidates = search_media(term, video=True)
            candidates.sort(key=lambda c: relevance(c, [term]), reverse=True)
            for candidate in candidates:
                if candidate["url"] not in used_urls:
                    selected.append(candidate)
                    used_urls.add(candidate["url"])
                    break
        except Exception as exc:
            print(f"Video search failed for {term}: {exc}")
        if len(selected) >= 10:
            break

    # If video coverage is weak, fill only the missing slots with relevant images.
    if len(selected) < 6:
        for term in terms:
            try:
                candidates = search_media(term, video=False)
                candidates.sort(key=lambda c: relevance(c, [term]), reverse=True)
                for candidate in candidates:
                    if candidate["url"] not in used_urls:
                        selected.append(candidate)
                        used_urls.add(candidate["url"])
                        break
            except Exception as exc:
                print(f"Image fallback failed for {term}: {exc}")
            if len(selected) >= 10:
                break

    sources = []
    found = 0
    for candidate in selected[:10]:
        try:
            path = download(candidate, found)
            sources.append({**candidate, "local_file": str(path.relative_to(ROOT))})
            found += 1
        except Exception as exc:
            print(f"Download failed for {candidate['title']}: {exc}")

    (VISUALS / "sources.txt").write_text(
        "\n".join(
            f"{s['local_file']} | {s['title']} | {s['artist']} | {s['license']} | {s['pageurl']} | {s['url']}"
            for s in sources
        ), encoding="utf-8"
    )
    print(f"Downloaded {found} relevant reusable visuals ({sum(s['mime'] in VIDEO_MIMES for s in sources)} videos)")


if __name__ == "__main__":
    main()
