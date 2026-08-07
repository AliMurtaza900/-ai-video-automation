import html
import re
import time
from pathlib import Path
from urllib.parse import quote
import requests

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
ASSETS = ROOT / "assets"
VISUALS = ASSETS / "visuals"
VISUALS.mkdir(parents=True, exist_ok=True)

OPENVERSE_API = "https://api.openverse.org/v1/images/"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "AI-Video-Automation/4.0 (GitHub Actions)"}
VIDEO_MIMES = {"video/mp4", "video/webm", "video/ogg"}
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")
STOP = set("about after again because before could every first from have into more most never only other over really their there these this those through what when where which while with would your that than they them then were will also some many fact facts interesting people thing story stories history video videos footage of the and are was for not you but has had its our their documentary image images footage clip clips scene scenes photo photos picture pictures".split())


def clean(value):
    return re.sub(r"\s+", " ", html.unescape(re.sub("<.*?>", " ", value or ""))).strip()


def scene_sentences(script):
    parts = re.split(r"(?<=[.!?])\s+", script.strip())
    return [clean(s) for s in parts if clean(s)][:12]


def terms_for_scene(sentence):
    words = re.findall(r"[A-Za-z]{4,}", sentence.lower())
    out = []
    for word in words:
        if word not in STOP and word not in out:
            out.append(word)
    return out[:8] or ["documentary"]


def request_json(url, params):
    for attempt in range(4):
        try:
            response = requests.get(url, params=params, timeout=25, headers=UA)
            if response.status_code == 429:
                retry = response.headers.get("Retry-After")
                delay = int(retry) if retry and retry.isdigit() else min(30, 3 * (2 ** attempt))
                print(f"Rate limited by {url}; waiting {delay}s")
                time.sleep(delay)
                continue
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            if attempt < 3:
                delay = min(20, 2 * (2 ** attempt))
                print(f"Search error: {exc}; retrying in {delay}s")
                time.sleep(delay)
            else:
                print(f"Search failed after retries: {exc}")
    return {}


def openverse_search(query, limit=12):
    data = request_json(OPENVERSE_API, {"q": query, "page": 1, "page_size": limit, "mature": "false"})
    results = []
    for item in data.get("results", []):
        url = item.get("url")
        if not url:
            continue
        width, height = int(item.get("width") or 0), int(item.get("height") or 0)
        if width < 1000 or height < 700:
            continue
        results.append({
            "url": url,
            "mime": "image/jpeg" if str(item.get("filetype", "")).lower() in {"jpg", "jpeg"} else "image/png",
            "width": width,
            "height": height,
            "duration": 0,
            "title": clean(item.get("title", query)),
            "artist": clean(item.get("creator", "")),
            "license": clean(item.get("license", "")),
            "description": clean(" ".join(item.get("tags", []) if isinstance(item.get("tags"), list) else [])),
            "pageurl": item.get("foreign_landing_url") or item.get("detail_url", ""),
            "source": "Openverse",
        })
    return results


def commons_search(query, video=False, limit=10):
    params = {"action":"query","format":"json","generator":"search","gsrsearch":query,"gsrnamespace":6,"gsrlimit":limit,"prop":"imageinfo|info","iiprop":"url|mime|width|height|duration|extmetadata","inprop":"url"}
    data = request_json(COMMONS_API, params)
    results = []
    for page in data.get("query", {}).get("pages", {}).values():
        info = page.get("imageinfo", [{}])[0]
        url, mime = info.get("url"), info.get("mime", "")
        if not url:
            continue
        is_video = mime in VIDEO_MIMES
        if video != is_video:
            continue
        width, height = int(info.get("width") or 0), int(info.get("height") or 0)
        if width < 1000 or height < 700:
            continue
        meta = info.get("extmetadata", {})
        results.append({
            "url":url,"mime":mime,"width":width,"height":height,"duration":float(info.get("duration") or 0),
            "title":clean(meta.get("ObjectName",{}).get("value",page.get("title",query))),
            "artist":clean(meta.get("Artist",{}).get("value","")),
            "license":clean(meta.get("LicenseShortName",{}).get("value","")),
            "description":clean(meta.get("ImageDescription",{}).get("value","")),
            "pageurl":page.get("fullurl",f"https://commons.wikimedia.org/wiki/{quote(page.get('title',''))}"),
            "source":"Wikimedia Commons",
        })
    return results


def score(candidate, terms, scene, prefer_video=False):
    title = candidate["title"].lower()
    desc = candidate["description"].lower()
    scene_words = set(re.findall(r"[a-z]{4,}", scene.lower())) - STOP
    value = 0
    for term in terms:
        if term in title: value += 22
        elif term in desc: value += 8
    value += min(30, sum(3 for word in scene_words if word in title or word in desc))
    if candidate["mime"] in VIDEO_MIMES:
        value += 45 if prefer_video else 15
        if candidate["duration"] >= 4: value += 8
        if candidate["duration"] >= 8: value += 5
    pixels = candidate["width"] * candidate["height"]
    if pixels >= 3840 * 2160: value += 15
    elif pixels >= 1920 * 1080: value += 10
    elif pixels >= 1280 * 720: value += 5
    if candidate["license"]: value += 4
    return value


def download(candidate, index):
    response = requests.get(candidate["url"], timeout=120, headers=UA, stream=True)
    response.raise_for_status()
    mime = candidate["mime"]
    suffix = ".mp4" if mime == "video/mp4" else ".webm" if mime == "video/webm" else ".ogg" if mime == "video/ogg" else ".jpg"
    path = VISUALS / f"visual_{index:02d}{suffix}"
    total = 0
    with path.open("wb") as file:
        for chunk in response.iter_content(1024 * 1024):
            if chunk:
                file.write(chunk); total += len(chunk)
                if total > 150 * 1024 * 1024:
                    path.unlink(missing_ok=True); raise RuntimeError("media exceeds 150 MB")
    if total < 50000:
        path.unlink(missing_ok=True); raise RuntimeError("media too small")
    return path


def make_local_fallback(index, scene):
    # Emergency-only fallback. It deliberately contains no narration text so
    # the video never turns into a wall of text when providers are unavailable.
    path = VISUALS / f"visual_{index:02d}.svg"
    svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0b1020"/><stop offset="0.5" stop-color="#172554"/><stop offset="1" stop-color="#0f766e"/></linearGradient><radialGradient id="r"><stop offset="0" stop-color="#ffffff" stop-opacity=".25"/><stop offset="1" stop-color="#ffffff" stop-opacity="0"/></radialGradient></defs><rect width="1080" height="1920" fill="url(#g)"/><circle cx="820" cy="420" r="520" fill="url(#r)"/><circle cx="180" cy="1520" r="600" fill="#ffffff" opacity=".06"/><path d="M0 1500 C260 1320 440 1680 700 1470 S930 1270 1080 1390 L1080 1920 L0 1920Z" fill="#000" opacity=".18"/></svg>'''
    path.write_text(svg, encoding="utf-8")
    return path


def search_candidates(scene, terms, video):
    # Openverse is the primary image source because it aggregates many openly
    # licensed providers. Wikimedia remains a secondary source and a video
    # source. Keep queries short to improve relevance and API stability.
    queries = [
        " ".join(terms[:6]),
        " ".join(terms[:5]),
        " ".join(terms[:4]),
    ]
    candidates, seen = [], set()
    for query in queries:
        if video:
            found = commons_search(query, video=True, limit=8)
        else:
            found = openverse_search(query, limit=10) + commons_search(query, video=False, limit=6)
        for candidate in found:
            if candidate["url"] not in seen:
                seen.add(candidate["url"]); candidates.append(candidate)
    return sorted(candidates, key=lambda x: score(x, terms, scene, video), reverse=True)


def main():
    script_path = OUTPUT / "script.txt"
    if not script_path.exists(): raise RuntimeError("Generated script is missing")
    script = script_path.read_text(encoding="utf-8").strip()
    if not script: raise RuntimeError("Generated script is empty")

    for path in VISUALS.glob("visual_*"): path.unlink()
    (VISUALS / "sources.txt").unlink(missing_ok=True)

    scenes = scene_sentences(script)
    selected, used, sources = [], set(), []

    for scene_index, scene in enumerate(scenes, 1):
        terms = terms_for_scene(scene)
        chosen = None

        # First choice: real video footage with strong scene relevance.
        for candidate in search_candidates(scene, terms, True):
            if candidate["url"] not in used and score(candidate, terms, scene, True) >= 32:
                chosen = candidate; break

        # Second choice: high-resolution, openly licensed photographs.
        if chosen is None:
            for candidate in search_candidates(scene, terms, False):
                if candidate["url"] not in used and score(candidate, terms, scene) >= 20:
                    chosen = candidate; break

        # Last resort: a visually rich generated background. This is never
        # allowed to contain narration text.
        if chosen is None:
            path = make_local_fallback(len(selected), scene)
            selected.append(path)
            sources.append({"scene":scene_index,"scene_text":scene,"local_file":str(path.relative_to(ROOT)),"title":"Emergency visual fallback","artist":"AI Video Automation","license":"Generated locally","pageurl":"","url":"","mime":"image/svg+xml","score":0,"source":"Local"})
            print(f"Scene {scene_index}: no external visual match; emergency visual fallback")
            continue

        try:
            path = download(chosen, len(selected))
        except Exception as exc:
            print(f"Scene {scene_index}: selected media failed ({exc}); trying alternate")
            path = None
            for candidate in search_candidates(scene, terms, chosen["mime"] in VIDEO_MIMES):
                if candidate["url"] in used: continue
                try:
                    path = download(candidate, len(selected)); chosen = candidate; break
                except Exception: continue
            if path is None:
                path = make_local_fallback(len(selected), scene); chosen = None

        if chosen:
            used.add(chosen["url"])
            value = score(chosen, terms, scene, chosen["mime"] in VIDEO_MIMES)
            sources.append({**chosen,"scene":scene_index,"scene_text":scene,"local_file":str(path.relative_to(ROOT)),"score":value})
            print(f"Scene {scene_index}: {chosen['title']} | source={chosen['source']} | score={value} | {chosen['width']}x{chosen['height']}")
        else:
            sources.append({"scene":scene_index,"scene_text":scene,"local_file":str(path.relative_to(ROOT)),"title":"Emergency visual fallback","artist":"AI Video Automation","license":"Generated locally","pageurl":"","url":"","mime":"image/svg+xml","score":0,"source":"Local"})
        selected.append(path)

    if not selected: selected.append(make_local_fallback(0, scenes[0] if scenes else "Interesting fact"))

    (VISUALS / "sources.txt").write_text(
        "\n".join(f"Scene {s['scene']} | score={s['score']} | source={s['source']} | {s['local_file']} | {s['title']} | {s['artist']} | {s['license']} | {s['pageurl']} | {s['url']}" for s in sources),
        encoding="utf-8",
    )
    videos = sum(s["mime"] in VIDEO_MIMES for s in sources)
    fallbacks = sum(s["source"] == "Local" for s in sources)
    print(f"VISUAL_REPORT videos={videos} images={len(sources)-videos-fallbacks} fallbacks={fallbacks} total={len(sources)} scenes={len(scenes)}")


if __name__ == "__main__":
    main()
