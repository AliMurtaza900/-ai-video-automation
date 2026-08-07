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
UA = {"User-Agent": "AI-Video-Automation/3.2 (GitHub Actions)"}
VIDEO_MIMES = {"video/mp4", "video/webm", "video/ogg"}
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")
STOP = set("about after again because before could every first from have into more most never only other over really their there these this those through what when where which while with would your that than they them then were will also some many fact facts interesting people thing story stories history video videos footage of the and are was for not you but has had its our their documentary image images footage clip clips scene scenes".split())


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


def search_media(query, video=True, limit=15):
    params = {
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": query, "gsrnamespace": 6, "gsrlimit": limit,
        "prop": "imageinfo|info", "iiprop": "url|mime|size|width|height|duration|extmetadata",
        "inprop": "url",
    }
    for attempt in range(4):
        try:
            response = requests.get(COMMONS_API, params=params, timeout=25, headers=UA)
            if response.status_code == 429:
                retry = response.headers.get("Retry-After")
                delay = int(retry) if retry and retry.isdigit() else min(30, 3 * (2 ** attempt))
                print(f"Wikimedia rate limited; waiting {delay}s")
                time.sleep(delay)
                continue
            response.raise_for_status()
            pages = response.json().get("query", {}).get("pages", {})
            result = []
            for page in pages.values():
                info = page.get("imageinfo", [{}])[0]
                url, mime = info.get("url"), info.get("mime", "")
                if not url:
                    continue
                is_video = mime in VIDEO_MIMES
                if video and not is_video:
                    continue
                if not video and (is_video or not url.lower().split("?")[0].endswith(IMAGE_EXTS)):
                    continue
                width = int(info.get("width") or 0)
                height = int(info.get("height") or 0)
                duration = float(info.get("duration") or 0)
                # Reject genuinely tiny assets. For vertical output we still
                # prefer large landscape footage because the renderer crops it.
                if width < 720 or height < 480:
                    continue
                meta = info.get("extmetadata", {})
                result.append({
                    "url": url,
                    "mime": mime,
                    "width": width,
                    "height": height,
                    "duration": duration,
                    "title": clean(meta.get("ObjectName", {}).get("value", page.get("title", query))),
                    "artist": clean(meta.get("Artist", {}).get("value", "")),
                    "license": clean(meta.get("LicenseShortName", {}).get("value", "")),
                    "description": clean(meta.get("ImageDescription", {}).get("value", "")),
                    "pageurl": page.get("fullurl", f"https://commons.wikimedia.org/wiki/{quote(page.get('title',''))}"),
                })
            return result
        except Exception as exc:
            if attempt < 3:
                delay = min(20, 2 * (2 ** attempt))
                print(f"Search error for '{query}': {exc}; retrying in {delay}s")
                time.sleep(delay)
            else:
                print(f"Search failed for '{query}': {exc}")
    return []


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

    # Strongly prefer actual moving footage, and reward footage long enough
    # to survive a few seconds of cropping without looking like a still.
    if candidate["mime"] in VIDEO_MIMES:
        value += 45 if prefer_video else 15
        if candidate["duration"] >= 4:
            value += 8
        if candidate["duration"] >= 8:
            value += 5

    # Resolution matters for a 1080x1920 output. Reward high-resolution media.
    pixels = candidate["width"] * candidate["height"]
    if pixels >= 1920 * 1080:
        value += 12
    elif pixels >= 1280 * 720:
        value += 6

    if candidate["license"]:
        value += 3
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
                file.write(chunk)
                total += len(chunk)
                if total > 150 * 1024 * 1024:
                    path.unlink(missing_ok=True)
                    raise RuntimeError("media exceeds 150 MB")
    if total < 50000:
        path.unlink(missing_ok=True)
        raise RuntimeError("media too small")
    return path


def make_local_fallback(index, scene):
    path = VISUALS / f"visual_{index:02d}.svg"
    safe = html.escape(scene[:140])
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#111827"/><stop offset="1" stop-color="#374151"/></linearGradient></defs><rect width="1080" height="1920" fill="url(#g)"/><circle cx="850" cy="350" r="260" fill="white" opacity=".08"/><circle cx="220" cy="1600" r="360" fill="white" opacity=".06"/><text x="80" y="880" fill="white" font-family="DejaVu Sans" font-size="46" font-weight="bold">AI DOCUMENTARY</text><text x="80" y="960" fill="#d1d5db" font-family="DejaVu Sans" font-size="28">{safe}</text></svg>'''
    path.write_text(svg, encoding="utf-8")
    return path


def search_candidates(scene, terms, video):
    # Query variants keep scene-specific entities while progressively adding
    # useful visual-context words. This is much more precise than searching
    # the entire narration paragraph.
    context = ["footage", "video", "documentary"] if video else ["photo", "photograph"]
    queries = [
        " ".join(terms[:6] + context[:1]),
        " ".join(terms[:5] + context[:1]),
        " ".join(terms[:4] + context[:1]),
        " ".join(terms[:3] + context[:1]),
    ]
    candidates, seen = [], set()
    for query in queries:
        for candidate in search_media(query, video):
            if candidate["url"] not in seen:
                seen.add(candidate["url"])
                candidates.append(candidate)
    return sorted(candidates, key=lambda x: score(x, terms, scene, video), reverse=True)


def main():
    script_path = OUTPUT / "script.txt"
    if not script_path.exists():
        raise RuntimeError("Generated script is missing")
    script = script_path.read_text(encoding="utf-8").strip()
    if not script:
        raise RuntimeError("Generated script is empty")

    for path in VISUALS.glob("visual_*"):
        path.unlink()
    (VISUALS / "sources.txt").unlink(missing_ok=True)

    scenes = scene_sentences(script)
    selected, used, sources = [], set(), []

    for scene_index, scene in enumerate(scenes, 1):
        terms = terms_for_scene(scene)
        chosen = None

        # Quality bar for moving footage: don't accept a generic clip just
        # because it exists. Relevance + resolution must clear the threshold.
        for candidate in search_candidates(scene, terms, True):
            if candidate["url"] not in used and score(candidate, terms, scene, True) >= 35:
                chosen = candidate
                break

        # Still images are a deliberate second tier, not the default.
        if chosen is None:
            for candidate in search_candidates(scene, terms, False):
                if candidate["url"] not in used and score(candidate, terms, scene) >= 18:
                    chosen = candidate
                    break

        # One conservative broad search when scene-specific coverage is weak.
        # We do not use generic footage if it cannot meet a meaningful score.
        if chosen is None:
            for query in ("documentary footage", "nature footage", "city footage"):
                candidates = search_media(query, True, 10)
                candidates = sorted(candidates, key=lambda x: score(x, terms, scene, True), reverse=True)
                candidate = next((c for c in candidates if c["url"] not in used and score(c, terms, scene, True) >= 28), None)
                if candidate:
                    chosen = candidate
                    break

        if chosen is None:
            path = make_local_fallback(len(selected), scene)
            selected.append(path)
            sources.append({
                "scene": scene_index,
                "scene_text": scene,
                "local_file": str(path.relative_to(ROOT)),
                "title": "Local guaranteed fallback visual",
                "artist": "AI Video Automation",
                "license": "Generated locally",
                "pageurl": "",
                "url": "",
                "mime": "image/svg+xml",
                "score": 0,
            })
            print(f"Scene {scene_index}: no quality external match; using local fallback")
            continue

        try:
            path = download(chosen, len(selected))
        except Exception as exc:
            print(f"Scene {scene_index} download failed: {exc}; trying next candidate")
            alternatives = [
                c for c in search_candidates(scene, terms, chosen["mime"] in VIDEO_MIMES)
                if c["url"] not in used and c["url"] != chosen["url"]
            ]
            path = None
            for candidate in alternatives:
                try:
                    path = download(candidate, len(selected))
                    chosen = candidate
                    break
                except Exception:
                    continue
            if path is None:
                path = make_local_fallback(len(selected), scene)
                chosen = None

        if chosen:
            used.add(chosen["url"])
            value = score(chosen, terms, scene, chosen["mime"] in VIDEO_MIMES)
            sources.append({
                **chosen,
                "scene": scene_index,
                "scene_text": scene,
                "local_file": str(path.relative_to(ROOT)),
                "score": value,
            })
            print(f"Scene {scene_index}: {chosen['title']} (score={value}, {chosen['width']}x{chosen['height']}, mime={chosen['mime']})")
        else:
            sources.append({
                "scene": scene_index,
                "scene_text": scene,
                "local_file": str(path.relative_to(ROOT)),
                "title": "Local guaranteed fallback visual",
                "artist": "AI Video Automation",
                "license": "Generated locally",
                "pageurl": "",
                "url": "",
                "mime": "image/svg+xml",
                "score": 0,
            })
        selected.append(path)

    if not selected:
        selected.append(make_local_fallback(0, scenes[0] if scenes else "Interesting fact"))

    (VISUALS / "sources.txt").write_text(
        "\n".join(
            f"Scene {s['scene']} | score={s['score']} | {s['local_file']} | {s['title']} | {s['artist']} | {s['license']} | {s['pageurl']} | {s['url']}"
            for s in sources
        ),
        encoding="utf-8",
    )
    videos = sum(s["mime"] in VIDEO_MIMES for s in sources)
    fallbacks = sum(s["mime"] == "image/svg+xml" for s in sources)
    print(f"VISUAL_REPORT videos={videos} images={len(sources)-videos-fallbacks} fallbacks={fallbacks} total={len(sources)} scenes={len(scenes)}")


if __name__ == "__main__":
    main()
