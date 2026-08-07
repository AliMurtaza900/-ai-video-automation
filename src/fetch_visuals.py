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

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
OPENVERSE_API = "https://api.openverse.org/v1/images/"
UA = {"User-Agent": "AI-Video-Automation/3.4 (GitHub Actions)"}
VIDEO_MIMES = {"video/mp4", "video/webm", "video/ogg"}
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")
STOP = set("about after again because before could every first from have into more most never only other over really their there these this those through what when where which while with would your that than they them then were will also some many fact facts interesting people thing story stories history video videos footage of the and are was for not you but has had its our their documentary image images clip clips scene scenes".split())


def clean(value):
    return re.sub(r"\s+", " ", html.unescape(re.sub("<.*?>", " ", str(value or "")))).strip()


def request_json(url, params, attempts=4):
    for attempt in range(attempts):
        try:
            response = requests.get(url, params=params, timeout=25, headers=UA)
            if response.status_code == 429:
                retry = response.headers.get("Retry-After")
                delay = int(retry) if retry and retry.isdigit() else min(60, 4 * (2 ** attempt))
                print(f"Rate limited by {url}; waiting {delay}s")
                time.sleep(delay)
                continue
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            if attempt == attempts - 1:
                print(f"Request failed for {url}: {exc}")
                return {}
            delay = min(20, 2 * (2 ** attempt))
            print(f"Request error: {exc}; retrying in {delay}s")
            time.sleep(delay)
    return {}


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


def normalize_tags(tags):
    if not isinstance(tags, list):
        return []
    values = []
    for tag in tags:
        if isinstance(tag, str):
            values.append(tag)
        elif isinstance(tag, dict):
            for key in ("name", "title", "tag", "label"):
                if isinstance(tag.get(key), str):
                    values.append(tag[key])
                    break
    return values


def openverse_search(query, limit=12):
    try:
        data = request_json(OPENVERSE_API, {"q": query, "page": 1, "page_size": limit, "mature": "false"})
    except Exception as exc:
        print(f"Openverse search failed for '{query}': {exc}")
        return []
    results = []
    for item in data.get("results", []):
        url = item.get("url")
        if not url:
            continue
        try:
            width, height = int(item.get("width") or 0), int(item.get("height") or 0)
        except (TypeError, ValueError):
            width, height = 0, 0
        if width < 1000 or height < 700:
            continue
        tags = normalize_tags(item.get("tags"))
        results.append({
            "url": url,
            "mime": "image/jpeg" if str(item.get("filetype", "")).lower() in {"jpg", "jpeg"} else "image/png",
            "width": width,
            "height": height,
            "duration": 0,
            "title": clean(item.get("title", query)),
            "artist": clean(item.get("creator", "")),
            "license": clean(item.get("license", "")),
            "description": clean(" ".join(tags)),
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
        if not video and not url.lower().split("?")[0].endswith(IMAGE_EXTS):
            continue
        try:
            width, height = int(info.get("width") or 0), int(info.get("height") or 0)
        except (TypeError, ValueError):
            width, height = 0, 0
        if width < 720 or height < 480:
            continue
        meta = info.get("extmetadata", {})
        results.append({
            "url": url, "mime": mime, "width": width, "height": height,
            "duration": float(info.get("duration") or 0),
            "title": clean(meta.get("ObjectName", {}).get("value", page.get("title", query))),
            "artist": clean(meta.get("Artist", {}).get("value", "")),
            "license": clean(meta.get("LicenseShortName", {}).get("value", "")),
            "description": clean(meta.get("ImageDescription", {}).get("value", "")),
            "pageurl": page.get("fullurl", f"https://commons.wikimedia.org/wiki/{quote(page.get('title',''))}"),
            "source": "Wikimedia Commons",
        })
    return results


def score(candidate, terms, scene, prefer_video=False):
    title = candidate["title"].lower()
    desc = candidate["description"].lower()
    words = set(re.findall(r"[a-z]{4,}", scene.lower())) - STOP
    value = 0
    for term in terms:
        if term in title:
            value += 18
        elif term in desc:
            value += 7
    value += min(24, sum(3 for word in words if word in title or word in desc))
    if candidate["mime"] in VIDEO_MIMES:
        value += 45 if prefer_video else 15
        if candidate["duration"] >= 4: value += 8
        if candidate["duration"] >= 8: value += 5
    pixels = candidate["width"] * candidate["height"]
    if pixels >= 1920 * 1080: value += 12
    elif pixels >= 1280 * 720: value += 6
    if candidate["license"]: value += 3
    return value


def download(candidate, index):
    response = requests.get(candidate["url"], timeout=120, headers=UA, stream=True)
    response.raise_for_status()
    suffix = ".mp4" if candidate["mime"] == "video/mp4" else ".webm" if candidate["mime"] == "video/webm" else ".ogg" if candidate["mime"] == "video/ogg" else ".jpg"
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
    # Safety fallback only. It is graphical, not a narration text card.
    path = VISUALS / f"visual_{index:02d}.svg"
    svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#020617"/><stop offset=".5" stop-color="#1e3a8a"/><stop offset="1" stop-color="#4c1d95"/></linearGradient><radialGradient id="r"><stop offset="0" stop-color="#38bdf8" stop-opacity=".65"/><stop offset="1" stop-color="#38bdf8" stop-opacity="0"/></radialGradient></defs><rect width="1080" height="1920" fill="url(#g)"/><circle cx="820" cy="350" r="430" fill="url(#r)"/><circle cx="160" cy="1560" r="480" fill="#a78bfa" opacity=".12"/><path d="M0 1480 C260 1260 430 1710 700 1430 S980 1280 1080 1500 L1080 1920 L0 1920Z" fill="#000" opacity=".45"/><circle cx="190" cy="350" r="90" fill="#fff" opacity=".08"/><circle cx="360" cy="350" r="55" fill="#fff" opacity=".07"/><circle cx="490" cy="350" r="35" fill="#fff" opacity=".06"/></svg>'''
    path.write_text(svg, encoding="utf-8")
    return path


def search_candidates(scene, terms, video):
    context = ["footage", "video"] if video else ["photo", "photograph"]
    queries = [
        " ".join(terms[:6] + context[:1]),
        " ".join(terms[:5] + context[:1]),
        " ".join(terms[:4] + context[:1]),
    ]
    candidates, seen = [], set()
    for query in queries:
        found = []
        if not video:
            found.extend(openverse_search(query, limit=10))
        found.extend(commons_search(query, video=video, limit=6))
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
        terms = terms_for_scene(scene); chosen = None
        for candidate in search_candidates(scene, terms, True):
            if candidate["url"] not in used and score(candidate, terms, scene, True) >= 35:
                chosen = candidate; break
        if chosen is None:
            for candidate in search_candidates(scene, terms, False):
                if candidate["url"] not in used and score(candidate, terms, scene) >= 18:
                    chosen = candidate; break
        if chosen is None:
            for query in ("documentary footage", "nature footage", "city footage"):
                candidates = commons_search(query, video=True, limit=6)
                candidate = next((c for c in sorted(candidates, key=lambda x: score(x, terms, scene, True), reverse=True) if c["url"] not in used and score(c, terms, scene, True) >= 28), None)
                if candidate: chosen = candidate; break
        if chosen is None:
            path = make_local_fallback(len(selected), scene)
            selected.append(path)
            sources.append({"scene":scene_index,"scene_text":scene,"local_file":str(path.relative_to(ROOT)),"title":"Graphical local fallback","artist":"AI Video Automation","license":"Generated locally","pageurl":"","url":"","mime":"image/svg+xml","score":0})
            print(f"Scene {scene_index}: no external visual match; graphical fallback")
            continue
        try:
            path = download(chosen, len(selected))
        except Exception as exc:
            print(f"Scene {scene_index} download failed: {exc}; trying next candidate")
            path = None
            for candidate in search_candidates(scene, terms, chosen["mime"] in VIDEO_MIMES):
                if candidate["url"] in used: continue
                try:
                    path = download(candidate, len(selected)); chosen = candidate; break
                except Exception: continue
            if path is None:
                path = make_local_fallback(len(selected), scene); chosen = None
        if chosen:
            used.add(chosen["url"]); value = score(chosen, terms, scene, chosen["mime"] in VIDEO_MIMES)
            sources.append({**chosen,"scene":scene_index,"scene_text":scene,"local_file":str(path.relative_to(ROOT)),"score":value})
            print(f"Scene {scene_index}: {chosen['title']} (score={value}, {chosen['width']}x{chosen['height']}, {chosen['mime']})")
        else:
            sources.append({"scene":scene_index,"scene_text":scene,"local_file":str(path.relative_to(ROOT)),"title":"Graphical local fallback","artist":"AI Video Automation","license":"Generated locally","pageurl":"","url":"","mime":"image/svg+xml","score":0})
        selected.append(path)

    if not selected: selected.append(make_local_fallback(0, scenes[0] if scenes else "Interesting fact"))
    (VISUALS / "sources.txt").write_text("\n".join(f"Scene {s['scene']} | score={s['score']} | {s['local_file']} | {s['title']} | {s['artist']} | {s['license']} | {s['pageurl']} | {s['url']}" for s in sources), encoding="utf-8")
    videos = sum(s["mime"] in VIDEO_MIMES for s in sources)
    fallbacks = sum(s["mime"] == "image/svg+xml" for s in sources)
    print(f"VISUAL_REPORT videos={videos} images={len(sources)-videos-fallbacks} fallbacks={fallbacks} total={len(sources)} scenes={len(scenes)}")

if __name__ == "__main__": main()
