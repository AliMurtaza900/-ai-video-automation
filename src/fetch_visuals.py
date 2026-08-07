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

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "AI-Video-Automation/3.0"}
VIDEO_MIMES = {"video/mp4", "video/webm", "video/ogg"}
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")
STOP = set("about after again because before could every first from have into more most never only other over really their there these this those through what when where which while with would your that than they them then were will also some many fact facts interesting people thing story stories history video videos footage of the and are was for not you but has had its our their".split())


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
    return out[:7] or ["documentary"]


def search_media(query, video=True, limit=40):
    params = {
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": query, "gsrnamespace": 6, "gsrlimit": limit,
        "prop": "imageinfo|info", "iiprop": "url|mime|size|extmetadata",
        "inprop": "url",
    }
    response = requests.get(COMMONS_API, params=params, timeout=25, headers=UA)
    response.raise_for_status()
    pages = response.json().get("query", {}).get("pages", {})
    result = []
    for page in pages.values():
        info = page.get("imageinfo", [{}])[0]
        url = info.get("url")
        if not url:
            continue
        mime = info.get("mime", "")
        is_video = mime in VIDEO_MIMES
        if video and not is_video:
            continue
        if not video and (is_video or not url.lower().split("?")[0].endswith(IMAGE_EXTS)):
            continue
        meta = info.get("extmetadata", {})
        result.append({
            "url": url,
            "mime": mime,
            "title": clean(meta.get("ObjectName", {}).get("value", page.get("title", query))),
            "artist": clean(meta.get("Artist", {}).get("value", "")),
            "license": clean(meta.get("LicenseShortName", {}).get("value", "")),
            "description": clean(meta.get("ImageDescription", {}).get("value", "")),
            "pageurl": page.get("fullurl", f"https://commons.wikimedia.org/wiki/{quote(page.get('title',''))}"),
        })
    return result


def score(candidate, terms, scene, prefer_video=False):
    title = candidate["title"].lower()
    desc = candidate["description"].lower()
    scene_words = set(re.findall(r"[a-z]{4,}", scene.lower())) - STOP
    score = 0
    for term in terms:
        if term in title:
            score += 12
        elif term in desc:
            score += 5
    score += min(16, sum(2 for word in scene_words if word in title or word in desc))
    if candidate["mime"] in VIDEO_MIMES:
        score += 25 if prefer_video else 10
    if candidate["license"]:
        score += 3
    return score


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


def search_candidates(scene, terms, video):
    # Broad-to-specific searches give us several independent chances to find
    # usable public footage instead of failing on one overly-specific query.
    queries = [
        " ".join(terms[:5]),
        " ".join(terms[:4]),
        " ".join(terms[:3]),
        " ".join(terms[:2]),
    ]
    candidates, seen = [], set()
    for query in queries:
        try:
            for candidate in search_media(query, video):
                if candidate["url"] not in seen:
                    seen.add(candidate["url"])
                    candidates.append(candidate)
        except Exception as exc:
            print(f"Search failed for '{query}': {exc}")
    candidates.sort(key=lambda item: score(item, terms, scene, prefer_video=video), reverse=True)
    return candidates


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

    for scene_index, scene in enumerate(scenes, start=1):
        terms = terms_for_scene(scene)
        chosen = None

        # Tier 1: relevant public video.
        for candidate in search_candidates(scene, terms, True):
            if candidate["url"] not in used and score(candidate, terms, scene, True) >= 18:
                chosen = candidate
                break

        # Tier 2: relevant public still image. This keeps the video alive when
        # Commons has no suitable moving footage for a specific scene.
        if chosen is None:
            for candidate in search_candidates(scene, terms, False):
                if candidate["url"] not in used and score(candidate, terms, scene) >= 7:
                    chosen = candidate
                    break

        # Tier 3: broad documentary fallback. Never fail the entire render
        # because one scene has weak search coverage.
        if chosen is None:
            fallback_queries = ["documentary", "people", "nature", "city", "technology"]
            fallback_candidates = []
            for query in fallback_queries:
                try:
                    fallback_candidates.extend(search_media(query, True, 20))
                except Exception as exc:
                    print(f"Fallback search failed for '{query}': {exc}")
            fallback_candidates.sort(key=lambda item: score(item, terms, scene, True), reverse=True)
            chosen = next((c for c in fallback_candidates if c["url"] not in used), None)

        if chosen is None:
            print(f"Scene {scene_index}: no public visual found; scene will be represented by the renderer")
            continue

        try:
            path = download(chosen, len(selected))
        except Exception as exc:
            print(f"Scene {scene_index} download failed: {exc}")
            continue

        used.add(chosen["url"])
        selected.append(path)
        chosen_score = score(chosen, terms, scene, chosen["mime"] in VIDEO_MIMES)
        sources.append({**chosen, "scene": scene_index, "scene_text": scene,
                        "local_file": str(path.relative_to(ROOT)), "score": chosen_score})
        print(f"Scene {scene_index}: {chosen['title']} (score={chosen_score}, mime={chosen['mime']})")

    if not selected:
        raise RuntimeError("No public visuals could be downloaded")

    (VISUALS / "sources.txt").write_text(
        "\n".join(
            f"Scene {s['scene']} | score={s['score']} | {s['local_file']} | {s['title']} | {s['artist']} | {s['license']} | {s['pageurl']} | {s['url']}"
            for s in sources
        ),
        encoding="utf-8",
    )
    videos = sum(s["mime"] in VIDEO_MIMES for s in sources)
    print(f"VISUAL_REPORT videos={videos} images={len(sources)-videos} total={len(sources)} scenes={len(scenes)}")


if __name__ == "__main__":
    main()
