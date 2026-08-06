import re
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
ASSETS = ROOT / "assets"
VISUALS = ASSETS / "visuals"
VISUALS.mkdir(parents=True, exist_ok=True)

API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "AI-Video-Automation/1.0"}
VIDEO_MIMES = {"video/mp4", "video/webm", "video/ogg"}


def keywords(script):
    stop = {"about","after","again","because","before","could","every","first","from","have","into","more","most","never","only","other","over","really","their","there","these","this","those","through","what","when","where","which","while","with","would","your","that","than","they","them","then","were","will","also","some","many","fact","facts","interesting","people","thing"}
    words = re.findall(r"[A-Za-z]{4,}", script.lower())
    result = []
    for word in words:
        if word not in stop and word not in result:
            result.append(word)
        if len(result) >= 8:
            break
    return result


def search_video(term):
    params = {"action":"query","format":"json","generator":"search","gsrsearch":f"{term} filetype:video","gsrnamespace":6,"gsrlimit":8,"prop":"imageinfo","iiprop":"url|mime|extmetadata"}
    r = requests.get(API, params=params, timeout=20, headers=UA)
    r.raise_for_status()
    pages = r.json().get("query", {}).get("pages", {})
    for page in pages.values():
        info = page.get("imageinfo", [{}])[0]
        if info.get("mime") not in VIDEO_MIMES:
            continue
        url = info.get("url")
        if url:
            meta = info.get("extmetadata", {})
            return url, {"title":meta.get("ObjectName",{}).get("value",term),"artist":meta.get("Artist",{}).get("value",""),"license":meta.get("LicenseShortName",{}).get("value",""),"source":url}
    return None, None


def search_image(term):
    params = {"action":"query","format":"json","generator":"search","gsrsearch":term,"gsrnamespace":6,"gsrlimit":5,"prop":"imageinfo","iiprop":"url","iiurlwidth":1080}
    r = requests.get(API, params=params, timeout=20, headers=UA)
    r.raise_for_status()
    pages = r.json().get("query", {}).get("pages", {})
    for page in pages.values():
        info = page.get("imageinfo", [{}])[0]
        url = info.get("thumburl") or info.get("url")
        if url and url.lower().split("?")[0].endswith((".jpg",".jpeg",".png",".webp")):
            return url
    return None


def main():
    script = (OUTPUT / "script.txt").read_text(encoding="utf-8").strip()
    for old in VISUALS.glob("visual_*"):
        old.unlink()
    for old in VISUALS.glob("*.txt"):
        old.unlink()

    found = 0
    sources = []
    for term in keywords(script):
        try:
            url, meta = search_video(term)
            if url:
                suffix = ".webm" if ".webm" in url.lower() else ".mp4"
                data = requests.get(url, timeout=90, headers=UA).content
                if len(data) > 100_000:
                    (VISUALS / f"visual_{found:02d}{suffix}").write_bytes(data)
                    sources.append(meta)
                    found += 1
            if found >= 8:
                break
        except Exception as exc:
            print(f"Video search failed for {term}: {exc}")

    if found < 4:
        for term in keywords(script):
            if found >= 8:
                break
            try:
                url = search_image(term)
                if not url:
                    continue
                data = requests.get(url, timeout=30, headers=UA).content
                (VISUALS / f"visual_{found:02d}.jpg").write_bytes(data)
                found += 1
            except Exception as exc:
                print(f"Image fallback failed for {term}: {exc}")

    (VISUALS / "sources.txt").write_text("\n".join(f"{s.get('title','')} | {s.get('artist','')} | {s.get('license','')} | {s.get('source','')}" for s in sources), encoding="utf-8")
    print(f"Downloaded {found} Wikimedia Commons visuals ({len(sources)} video clips)")


if __name__ == "__main__":
    main()
