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
UA = {"User-Agent": "AI-Video-Automation/1.2"}
VIDEO_MIMES = {"video/mp4", "video/webm", "video/ogg"}
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")
STOP = set("about after again because before could every first from have into more most never only other over really their there these this those through what when where which while with would your that than they them then were will also some many fact facts interesting people thing story stories history".split())


def clean(value):
    return re.sub(r"\s+", " ", html.unescape(re.sub("<.*?>", " ", value or ""))).strip()


def scene_sentences(script):
    return [clean(s) for s in re.split(r"(?<=[.!?])\s+", script.strip()) if clean(s)][:12]


def terms_for_scene(sentence):
    words = re.findall(r"[A-Za-z]{4,}", sentence.lower())
    out = []
    for w in words:
        if w not in STOP and w not in out:
            out.append(w)
    return out[:5] or ["documentary"]


def search_media(query, video=True):
    q = f"{query} filetype:video" if video else query
    params = {"action":"query","format":"json","generator":"search","gsrsearch":q,"gsrnamespace":6,"gsrlimit":12,"prop":"imageinfo|info","iiprop":"url|mime|size|extmetadata","inprop":"url"}
    r = requests.get(API, params=params, timeout=20, headers=UA)
    r.raise_for_status()
    pages = r.json().get("query", {}).get("pages", {})
    result = []
    for page in pages.values():
        info = page.get("imageinfo", [{}])[0]
        url = info.get("url")
        if not url:
            continue
        mime = info.get("mime", "")
        if video and mime not in VIDEO_MIMES:
            continue
        if not video and not url.lower().split("?")[0].endswith(IMAGE_EXTS):
            continue
        meta = info.get("extmetadata", {})
        result.append({"url": url, "mime": mime,
                       "title": clean(meta.get("ObjectName", {}).get("value", page.get("title", query))),
                       "artist": clean(meta.get("Artist", {}).get("value", "")),
                       "license": clean(meta.get("LicenseShortName", {}).get("value", "")),
                       "description": clean(meta.get("ImageDescription", {}).get("value", "")),
                       "pageurl": page.get("fullurl", f"https://commons.wikimedia.org/wiki/{quote(page.get('title',''))}")})
    return result


def score(c, terms):
    title, desc = c["title"].lower(), c["description"].lower()
    value = sum(5 if t in title else 2 if t in desc else 0 for t in terms)
    if c["mime"] in VIDEO_MIMES:
        value += 5
    if c["license"]:
        value += 2
    return value


def download(c, index):
    r = requests.get(c["url"], timeout=120, headers=UA, stream=True)
    r.raise_for_status()
    suffix = ".webm" if c["mime"] == "video/webm" else ".mp4" if c["mime"] == "video/mp4" else ".jpg"
    path = VISUALS / f"visual_{index:02d}{suffix}"
    total = 0
    with path.open("wb") as f:
        for chunk in r.iter_content(1024 * 1024):
            if chunk:
                f.write(chunk)
                total += len(chunk)
                if total > 150 * 1024 * 1024:
                    raise RuntimeError("media exceeds 150 MB")
    if total < 50000:
        path.unlink(missing_ok=True)
        raise RuntimeError("media too small")
    return path


def main():
    script = (OUTPUT / "script.txt").read_text(encoding="utf-8").strip()
    if not script:
        raise RuntimeError("Generated script is empty")
    for p in VISUALS.glob("visual_*"):
        p.unlink()
    for p in VISUALS.glob("*.txt"):
        p.unlink()

    scenes = scene_sentences(script)
    selected, used, sources = [], set(), []
    for scene_index, sentence in enumerate(scenes):
        terms = terms_for_scene(sentence)
        query = " ".join(terms[:3])
        try:
            candidates = search_media(query, True)
        except Exception as e:
            print(f"Scene {scene_index + 1} video search failed: {e}")
            candidates = []
        candidates.sort(key=lambda c: score(c, terms), reverse=True)
        if not candidates:
            try:
                candidates = search_media(query, False)
            except Exception as e:
                print(f"Scene {scene_index + 1} image search failed: {e}")
                candidates = []
            candidates.sort(key=lambda c: score(c, terms), reverse=True)
        chosen = next((c for c in candidates if c["url"] not in used), None)
        if not chosen:
            continue
        try:
            path = download(chosen, len(selected))
            used.add(chosen["url"])
            selected.append(path)
            sources.append({**chosen, "scene": scene_index + 1, "scene_text": sentence, "local_file": str(path.relative_to(ROOT))})
            print(f"Scene {scene_index + 1}: {chosen['title']}")
        except Exception as e:
            print(f"Scene {scene_index + 1} download failed: {e}")

    (VISUALS / "sources.txt").write_text("\n".join(
        f"Scene {s['scene']} | {s['local_file']} | {s['title']} | {s['artist']} | {s['license']} | {s['pageurl']} | {s['url']}"
        for s in sources), encoding="utf-8")
    print(f"Created {len(selected)} scene-matched visuals for {len(scenes)} narration scenes")


if __name__ == "__main__":
    main()
