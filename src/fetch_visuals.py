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
UA = {"User-Agent": "AI-Video-Automation/2.0"}
VIDEO_MIMES = {"video/mp4", "video/webm", "video/ogg"}
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")
STOP = set("about after again because before could every first from have into more most never only other over really their there these this those through what when where which while with would your that than they them then were will also some many fact facts interesting people thing story stories history video videos footage footage of the".split())


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
    return out[:6] or ["documentary"]


def search_media(query, video=True):
    # Commons search works better with natural phrases than a literal
    # filetype:video suffix. Ask for multimedia and filter by MIME locally.
    params = {
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": query, "gsrnamespace": 6, "gsrlimit": 30,
        "prop": "imageinfo|info",
        "iiprop": "url|mime|size|extmetadata",
        "inprop": "url",
    }
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


def score(candidate, terms, scene):
    title = candidate["title"].lower()
    desc = candidate["description"].lower()
    scene_words = set(re.findall(r"[a-z]{4,}", scene.lower())) - STOP
    value = 0
    for term in terms:
        if term in title:
            value += 10
        elif term in desc:
            value += 4
    # Reward candidates whose metadata contains several scene-specific words.
    value += min(12, sum(2 for word in scene_words if word in title or word in desc))
    if candidate["mime"] in VIDEO_MIMES:
        value += 20
    if candidate["license"]:
        value += 3
    return value


def download(candidate, index):
    r = requests.get(candidate["url"], timeout=120, headers=UA, stream=True)
    r.raise_for_status()
    suffix = ".webm" if candidate["mime"] == "video/webm" else ".mp4" if candidate["mime"] == "video/mp4" else ".ogg" if candidate["mime"] == "video/ogg" else ".jpg"
    path = VISUALS / f"visual_{index:02d}{suffix}"
    total = 0
    with path.open("wb") as f:
        for chunk in r.iter_content(1024 * 1024):
            if chunk:
                f.write(chunk)
                total += len(chunk)
                if total > 150 * 1024 * 1024:
                    path.unlink(missing_ok=True)
                    raise RuntimeError("media exceeds 150 MB")
    if total < 50000:
        path.unlink(missing_ok=True)
        raise RuntimeError("media too small")
    return path


def candidates_for_scene(scene, terms, video):
    queries = [
        " ".join(terms[:4]),
        " ".join(terms[:3]),
        " ".join(terms[:2]),
    ]
    seen = set()
    candidates = []
    for query in queries:
        try:
            for candidate in search_media(query, video):
                if candidate["url"] not in seen:
                    seen.add(candidate["url"])
                    candidates.append(candidate)
        except Exception as exc:
            print(f"Search failed for '{query}': {exc}")
    candidates.sort(key=lambda c: score(c, terms, scene), reverse=True)
    return candidates


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

    for scene_index, scene in enumerate(scenes):
        terms = terms_for_scene(scene)
        # Prefer real moving footage. Only fall back to still images when a
        # scene has no usable video candidates.
        candidates = candidates_for_scene(scene, terms, True)
        chosen = next((c for c in candidates if c["url"] not in used and score(c, terms, scene) >= 20), None)

        if not chosen:
            candidates = candidates_for_scene(scene, terms, False)
            chosen = next((c for c in candidates if c["url"] not in used and score(c, terms, scene) >= 8), None)

        if not chosen:
            print(f"Scene {scene_index + 1}: no sufficiently relevant public visual found")
            continue

        try:
            path = download(chosen, len(selected))
            used.add(chosen["url"])
            selected.append(path)
            sources.append({
                **chosen,
                "scene": scene_index + 1,
                "scene_text": scene,
                "local_file": str(path.relative_to(ROOT)),
                "score": score(chosen, terms, scene),
            })
            print(f"Scene {scene_index + 1}: {chosen['title']} (score={sources[-1]['score']})")
        except Exception as exc:
            print(f"Scene {scene_index + 1} download failed: {exc}")

    if not selected:
        raise RuntimeError("No sufficiently relevant public visuals were found")

    (VISUALS / "sources.txt").write_text(
        "\n".join(
            f"Scene {s['scene']} | score={s['score']} | {s['local_file']} | {s['title']} | {s['artist']} | {s['license']} | {s['pageurl']} | {s['url']}"
            for s in sources
        ),
        encoding="utf-8",
    )
    video_count = sum(p.suffix.lower() in VIDEO_MIMES for p in selected)
    image_count = len(selected) - video_count
    print(f"VISUAL_REPORT videos={video_count} images={image_count} total={len(selected)} scenes={len(scenes)}")


if __name__ == "__main__":
    main()
