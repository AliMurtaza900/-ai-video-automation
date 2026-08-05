import re
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
ASSETS = ROOT / "assets"
VISUALS = ASSETS / "visuals"
VISUALS.mkdir(parents=True, exist_ok=True)

API = "https://commons.wikimedia.org/w/api.php"


def keywords(script):
    stop = {
        "about", "after", "again", "because", "before", "could", "every",
        "first", "from", "have", "into", "more", "most", "never", "only",
        "other", "over", "really", "their", "there", "these", "this", "those",
        "through", "what", "when", "where", "which", "while", "with", "would",
        "your", "that", "than", "they", "them", "then", "were", "will", "also",
        "some", "many", "fact", "facts", "interesting", "people", "thing",
    }
    words = re.findall(r"[A-Za-z]{4,}", script.lower())
    result = []
    for word in words:
        if word not in stop and word not in result:
            result.append(word)
        if len(result) >= 6:
            break
    return result


def search_image(term):
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": term,
        "gsrnamespace": 6,
        "gsrlimit": 3,
        "prop": "imageinfo",
        "iiprop": "url",
        "iiurlwidth": 1080,
    }
    r = requests.get(API, params=params, timeout=20, headers={"User-Agent": "AI-Video-Automation/1.0"})
    r.raise_for_status()
    pages = r.json().get("query", {}).get("pages", {})
    for page in pages.values():
        info = page.get("imageinfo", [{}])[0]
        url = info.get("thumburl") or info.get("url")
        if url and url.lower().split("?")[0].endswith((".jpg", ".jpeg", ".png", ".webp")):
            return url
    return None


def main():
    script = (OUTPUT / "script.txt").read_text(encoding="utf-8").strip()
    for old in VISUALS.glob("visual_*"):
        old.unlink()

    found = 0
    for i, term in enumerate(keywords(script)):
        try:
            url = search_image(term)
            if not url:
                continue
            data = requests.get(url, timeout=30, headers={"User-Agent": "AI-Video-Automation/1.0"}).content
            path = VISUALS / f"visual_{found:02d}.jpg"
            path.write_bytes(data)
            found += 1
            if found >= 6:
                break
        except Exception as exc:
            print(f"Visual search failed for {term}: {exc}")

    print(f"Downloaded {found} free Wikimedia visuals")


if __name__ == "__main__":
    main()
