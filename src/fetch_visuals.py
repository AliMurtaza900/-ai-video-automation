import html
import os
import re
import time
from pathlib import Path
from urllib.parse import quote

import requests
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
ASSETS = ROOT / "assets"
VISUALS = ASSETS / "visuals"
VISUALS.mkdir(parents=True, exist_ok=True)
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
OPENVERSE_API = "https://api.openverse.org/v1/images/"
PINTEREST_SEARCH = "https://www.pinterest.com/search/pins/"
UA = {"User-Agent": "AI-Video-Automation/3.4 (GitHub Actions)"}
VIDEO_MIMES = {"video/mp4", "video/webm", "video/ogg"}
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")
MAX_VISUALS = 18
PINTEREST_ENABLED = os.getenv("PINTEREST_ENABLED", "true").lower() not in {"0", "false", "no", "off"}
OPENVERSE_ENABLED = os.getenv("OPENVERSE_ENABLED", "true").lower() not in {"0", "false", "no", "off"}
OPENVERSE_TIMEOUT = float(os.getenv("OPENVERSE_TIMEOUT", "5"))
OPENVERSE_MAX_FAILURES = int(os.getenv("OPENVERSE_MAX_FAILURES", "2"))
OPENVERSE_BUDGET_SECONDS = float(os.getenv("OPENVERSE_BUDGET_SECONDS", "25"))
_openverse_failures = 0
_openverse_started_at = time.monotonic()
_openverse_disabled_reason = ""
STOP = set("about after again because before could every first from have into more most never only other over really their there these this those through what when where which while with would your that than they them then were will also some many fact facts interesting people thing story stories history video videos footage of the and are was for not you but has had its our their documentary image images clip clips scene scenes".split())


def clean(value):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<.*?>", " ", str(value or "")))).strip()


def request_json(url, params, attempts=2, timeout=12):
    for attempt in range(attempts):
        try:
            response = requests.get(url, params=params, timeout=timeout, headers=UA)
            if response.status_code == 429:
                print(f"Rate limited by {url}; skipping")
                return {}
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            if attempt == attempts - 1:
                print(f"Request failed for {url}: {exc}")
                return {}
            delay = min(6, 2 * (2 ** attempt))
            print(f"Request error: {exc}; retrying in {delay}s")
            time.sleep(delay)
    return {}


def scene_sentences(script):
    parts = [clean(s) for s in re.split(r"(?<=[.!?])\s+", script.strip()) if clean(s)]
    scenes = []
    for part in parts:
        words = part.split()
        if len(words) > 11:
            chunk_size = max(7, (len(words) + 1) // 2)
            scenes.extend(" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size))
        else:
            scenes.append(part)
        if len(scenes) >= MAX_VISUALS:
            return scenes[:MAX_VISUALS]
    return scenes[:MAX_VISUALS]


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
    global _openverse_failures, _openverse_disabled_reason
    if not OPENVERSE_ENABLED or _openverse_failures >= OPENVERSE_MAX_FAILURES:
        return []
    elapsed = time.monotonic() - _openverse_started_at
    if elapsed >= OPENVERSE_BUDGET_SECONDS:
        _openverse_disabled_reason = f"budget exhausted after {elapsed:.1f}s"
        print(f"Openverse disabled: {_openverse_disabled_reason}")
        return []

    # Openverse is optional. Never let a slow third-party API consume the
    # production job: one short request, no retry, and a small global budget.
    data = request_json(
        OPENVERSE_API,
        {"q": query, "page": 1, "page_size": limit, "mature": "false"},
        attempts=1,
        timeout=max(1.0, OPENVERSE_TIMEOUT),
    )
    if not data:
        _openverse_failures += 1
        if _openverse_failures >= OPENVERSE_MAX_FAILURES:
            _openverse_disabled_reason = f"{_openverse_failures} consecutive failures"
            print(f"Openverse disabled for this run: {_openverse_disabled_reason}")
        return []

    _openverse_failures = 0
    results = []
    for item in data.get("results", []):
        url = item.get("url")
        if not url:
            continue
        try:
            width, height = int(item.get("width") or 0), int(item.get("height") or 0)
        except (TypeError, ValueError):
            width = height = 0
        if width < 900 or height < 600:
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
    params = {
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": query, "gsrnamespace": 6, "gsrlimit": limit,
        "prop": "imageinfo|info", "iiprop": "url|mime|width|height|duration|extmetadata",
        "inprop": "url",
    }
    data = request_json(COMMONS_API, params)
    results = []
    for page in data.get("query", {}).get("pages", {}).values():
        info = page.get("imageinfo", [{}])[0]
        url, mime = info.get("url"), info.get("mime", "")
        if not url or (video != (mime in VIDEO_MIMES)):
            continue
        if not video and not url.lower().split("?")[0].endswith(IMAGE_EXTS):
            continue
        try:
            width, height = int(info.get("width") or 0), int(info.get("height") or 0)
        except (TypeError, ValueError):
            width = height = 0
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
            "pageurl": page.get("fullurl", f"https://commons.wikimedia.org/wiki/{quote(page.get('title', ''))}"),
            "source": "Wikimedia Commons",
        })
    return results


def pinterest_search(query, limit=12):
    if not PINTEREST_ENABLED:
        return []
    try:
        response = requests.get(PINTEREST_SEARCH, params={"q": query}, timeout=12, headers=UA)
        response.raise_for_status()
        text = response.text
    except Exception as exc:
        print(f"Pinterest search failed for '{query}': {exc}")
        return []

    # Extract direct pin image URLs from Pinterest HTML/serialized state.
    urls = re.findall(r'https?://i\.pinimg\.com/[^"\s<]+', text)
    results, seen = [], set()
    for raw in urls:
        url = html.unescape(raw).replace("\\u002F", "/").replace("\\/", "/").replace("\\u003D", "=")
        url = url.split('"')[0].split("\\u0026")[0]
        if url in seen or not url.lower().split("?")[0].endswith(IMAGE_EXTS):
            continue
        seen.add(url)
        results.append({
            "url": url, "mime": "image/jpeg", "width": 0, "height": 0,
            "duration": 0, "title": query, "artist": "Pinterest",
            "license": "Unknown - verify before commercial use", "description": query,
            "pageurl": "https://www.pinterest.com/search/pins/?q=" + quote(query),
            "source": "Pinterest",
        })
        if len(results) >= limit:
            break
    return results


def score(candidate, terms, scene, prefer_video=False):
    title, desc = candidate["title"].lower(), candidate["description"].lower()
    words = set(re.findall(r"[a-z]{4,}", scene.lower())) - STOP
    value = sum(18 if term in title else 7 if term in desc else 0 for term in terms)
    value += min(24, sum(3 for word in words if word in title or word in desc))
    if candidate["mime"] in VIDEO_MIMES:
        value += 45 if prefer_video else 15
        if candidate["duration"] >= 4:
            value += 8
        if candidate["duration"] >= 8:
            value += 5
    pixels = candidate["width"] * candidate["height"]
    if pixels >= 1920 * 1080:
        value += 12
    elif pixels >= 1280 * 720:
        value += 6
    if candidate["license"]:
        value += 3
    if candidate["source"] == "Pinterest":
        value += 5
    return value


def download(candidate, index):
    response = requests.get(candidate["url"], timeout=(8, 20), headers=UA, stream=True)
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
    path = VISUALS / f"visual_{index:02d}.jpg"
    image = Image.new("RGB", (1080, 1920))
    draw = ImageDraw.Draw(image)
    for y in range(1920):
        t = y / 1919
        draw.line((0, y, 1080, y), fill=(int(8 + 28 * t), int(18 + 18 * (1 - t)), int(45 + 55 * (1 - t))))
    draw.ellipse((620, 100, 1260, 740), fill=(65, 135, 220))
    draw.ellipse((-300, 1320, 500, 2100), fill=(110, 65, 180))
    image.save(path, "JPEG", quality=90)
    return path


def discovery_queries(terms, video=False):
    context = "video footage" if video else "photo"
    core = terms[:6]
    queries = [" ".join(core + [context]), " ".join(terms[:5] + [context]), " ".join(terms[:4] + [context])]
    suffixes = [["close up", "detail"], ["wide shot", "landscape"], ["documentary", "archive"] if video else ["diagram", "illustration"]]
    for suffix in suffixes:
        queries.append(" ".join(terms[:4] + suffix))
    return list(dict.fromkeys(queries))


def search_candidates(scene, terms, video):
    candidates, seen = [], set()
    for query in discovery_queries(terms, video):
        if not video:
            found = pinterest_search(query, limit=8) + openverse_search(query, limit=10) + commons_search(query, video=False, limit=8)
        else:
            found = commons_search(query, video=True, limit=8)
        for candidate in found:
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
        for candidate in search_candidates(scene, terms, False):
            if candidate["url"] not in used and score(candidate, terms, scene) >= 18:
                chosen = candidate
                break
        if chosen is None:
            for candidate in search_candidates(scene, terms, True):
                if candidate["url"] not in used and score(candidate, terms, scene, True) >= 35:
                    chosen = candidate
                    break

        if chosen is None:
            path = make_local_fallback(len(selected), scene)
            selected.append(path)
            sources.append({"scene": scene_index, "scene_text": scene, "local_file": str(path.relative_to(ROOT)), "title": "Graphical local fallback", "artist": "AI Video Automation", "license": "Generated locally", "pageurl": "", "url": "", "mime": "image/jpeg", "score": 0})
            continue

        try:
            path = download(chosen, len(selected))
        except Exception as exc:
            print(f"Scene {scene_index} download failed: {exc}; trying alternatives")
            path = None
            for candidate in search_candidates(scene, terms, chosen["mime"] in VIDEO_MIMES):
                if candidate["url"] in used:
                    continue
                try:
                    path = download(candidate, len(selected))
                    chosen = candidate
                    break
                except Exception:
                    pass
            if path is None:
                path = make_local_fallback(len(selected), scene)
                chosen = None

        if chosen:
            used.add(chosen["url"])
            value = score(chosen, terms, scene, chosen["mime"] in VIDEO_MIMES)
            sources.append({**chosen, "scene": scene_index, "scene_text": scene, "local_file": str(path.relative_to(ROOT)), "score": value})
        else:
            sources.append({"scene": scene_index, "scene_text": scene, "local_file": str(path.relative_to(ROOT)), "title": "Graphical local fallback", "artist": "AI Video Automation", "license": "Generated locally", "pageurl": "", "url": "", "mime": "image/jpeg", "score": 0})
        selected.append(path)

    if not selected:
        selected.append(make_local_fallback(0, scenes[0] if scenes else "Interesting fact"))

    (VISUALS / "sources.txt").write_text(
        "\n".join(
            f"Scene {s['scene']} | source={s.get('source', 'local')} | score={s['score']} | {s['local_file']} | {s['title']} | {s['artist']} | {s['license']} | {s['pageurl']} | {s['url']}"
            for s in sources
        ),
        encoding="utf-8",
    )
    videos = sum(s["mime"] in VIDEO_MIMES for s in sources)
    fallbacks = sum("fallback" in s["title"].lower() for s in sources)
    pinterest = sum(s.get("source") == "Pinterest" for s in sources)
    print(f"VISUAL_REPORT videos={videos} images={len(sources) - videos - fallbacks} pinterest={pinterest} fallbacks={fallbacks} total={len(sources)} scenes={len(scenes)}")


if __name__ == "__main__":
    main()
