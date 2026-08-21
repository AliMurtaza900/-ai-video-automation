import hashlib
import html
import re
import time
from pathlib import Path
from urllib.parse import quote
import requests
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
VISUALS = ROOT / "assets" / "visuals"
VISUALS.mkdir(parents=True, exist_ok=True)
OPENVERSE = "https://api.openverse.org/v1/images/"
COMMONS = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "AI-Video-Automation/4.1 (+https://github.com/AliMurtaza900/-ai-video-automation)"}
STOP = set("about after again because before could every first from have into more most never only other over really their there these this those through what when where which while with would your that than they them then were will also some many fact facts interesting people thing story stories history video videos footage of the and are was for not you but has had its our their documentary image images clip clips scene scenes".split())


def clean(v):
    return re.sub(r"\s+", " ", html.unescape(re.sub("<.*?>", " ", str(v or "")))).strip()


def get(url, params, attempts=3):
    for i in range(attempts):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=20)
            if r.status_code == 429:
                time.sleep(min(20, 2 * (2 ** i)))
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if i == attempts - 1:
                print(f"Search failed: {e}")
                return {}
            time.sleep(min(8, 2 * (2 ** i)))
    return {}


def terms(sentence):
    words = re.findall(r"[A-Za-z]{4,}", sentence.lower())
    return [w for w in dict.fromkeys(words) if w not in STOP][:7] or ["science"]


def scenes(script):
    return [clean(x) for x in re.split(r"(?<=[.!?])\s+", script) if clean(x)][:12]


def openverse(q):
    data = get(OPENVERSE, {"q": q, "page_size": 20, "mature": "false"})
    out = []
    for x in data.get("results", []):
        url = x.get("url")
        if not url:
            continue
        try:
            w, h = int(x.get("width") or 0), int(x.get("height") or 0)
        except Exception:
            w, h = 0, 0
        if w < 640 or h < 360:
            continue
        tags = []
        for t in x.get("tags") or []:
            if isinstance(t, str):
                tags.append(t)
            elif isinstance(t, dict):
                for k in ("name", "title", "tag", "label"):
                    if isinstance(t.get(k), str):
                        tags.append(t[k])
                        break
        out.append({"url": url, "title": clean(x.get("title", q)), "desc": clean(" ".join(tags)), "artist": clean(x.get("creator")), "license": clean(x.get("license")), "page": x.get("foreign_landing_url") or x.get("detail_url", ""), "w": w, "h": h, "source": "Openverse"})
    return out


def commons(q):
    data = get(COMMONS, {"action": "query", "format": "json", "generator": "search", "gsrsearch": q, "gsrnamespace": 6, "gsrlimit": 15, "prop": "imageinfo|info", "iiprop": "url|mime|width|height|extmetadata", "inprop": "url"})
    out = []
    for p in data.get("query", {}).get("pages", {}).values():
        info = p.get("imageinfo", [{}])[0]
        url = info.get("url")
        mime = info.get("mime", "")
        if not url or not mime.startswith("image/"):
            continue
        try:
            w, h = int(info.get("width") or 0), int(info.get("height") or 0)
        except Exception:
            w, h = 0, 0
        if w < 640 or h < 360:
            continue
        meta = info.get("extmetadata", {})
        out.append({"url": url, "title": clean(meta.get("ObjectName", {}).get("value", p.get("title", q))), "desc": clean(meta.get("ImageDescription", {}).get("value", "")), "artist": clean(meta.get("Artist", {}).get("value", "")), "license": clean(meta.get("LicenseShortName", {}).get("value", "")), "page": p.get("fullurl", f"https://commons.wikimedia.org/wiki/{quote(p.get('title', ''))}"), "w": w, "h": h, "source": "Wikimedia Commons"})
    return out


def score(x, ts):
    text = (x["title"] + " " + x["desc"]).lower()
    s = 0
    for t in ts:
        if t in x["title"].lower():
            s += 20
        elif t in text:
            s += 7
    if x["w"] * x["h"] >= 1920 * 1080:
        s += 10
    elif x["w"] * x["h"] >= 1280 * 720:
        s += 5
    return s


def download(x, n):
    r = requests.get(x["url"], headers=UA, timeout=45, stream=True)
    r.raise_for_status()
    path = VISUALS / f"visual_{n:02d}.jpg"
    total = 0
    with path.open("wb") as f:
        for chunk in r.iter_content(1024 * 1024):
            if chunk:
                f.write(chunk)
                total += len(chunk)
            if total > 120 * 1024 * 1024:
                raise RuntimeError("visual too large")
    if total < 30000:
        path.unlink(missing_ok=True)
        raise RuntimeError("visual too small")
    # Validate the downloaded bytes before allowing them into the render stage.
    with Image.open(path) as im:
        im.verify()
    return path


def synthetic_visual(scene, n):
    """Create a deterministic cinematic fallback when public visual APIs are empty/unreachable.

    This is deliberately a real JPEG rather than a 1px placeholder so the renderer can
    continue producing a valid video. It is also deterministic per scene, which makes CI
    reruns reproducible.
    """
    digest = hashlib.sha256(scene.encode("utf-8")).digest()
    base = tuple(28 + digest[i] % 80 for i in range(3))
    accent = tuple(90 + digest[i + 3] % 120 for i in range(3))
    img = Image.new("RGB", (1080, 1920), base)
    draw = ImageDraw.Draw(img, "RGBA")

    # Soft cinematic light sources / depth layers.
    for radius, alpha, ox, oy in [(900, 42, 150, 420), (650, 34, 920, 1180), (500, 28, 350, 1650)]:
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer, "RGBA")
        ld.ellipse((ox - radius, oy - radius, ox + radius, oy + radius), fill=accent + (alpha,))
        layer = layer.filter(ImageFilter.GaussianBlur(radius // 3))
        img = Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")

    draw = ImageDraw.Draw(img, "RGBA")
    # Horizon and foreground silhouettes give the renderer something visually structured.
    horizon = 1160 + digest[6] % 260
    draw.rectangle((0, horizon, 1080, 1920), fill=(5, 8, 16, 115))
    for x in range(-80, 1180, 120):
        height = 120 + digest[(x // 120) % len(digest)] % 300
        draw.polygon([(x, horizon), (x + 55, horizon - height), (x + 130, horizon)], fill=(3, 5, 12, 150))

    # Minimal scene label; the actual narration remains in the normal caption layer.
    label = "SCENE %02d" % n
    draw.rounded_rectangle((55, 70, 330, 145), radius=24, fill=(0, 0, 0, 100))
    draw.text((82, 88), label, fill=(255, 255, 255, 220))
    path = VISUALS / f"visual_{n:02d}.jpg"
    img.save(path, "JPEG", quality=92, optimize=True)
    return path


def main():
    script_path = OUTPUT / "script.txt"
    script = script_path.read_text(encoding="utf-8").strip()
    for p in VISUALS.glob("visual_*"):
        p.unlink()

    scenes_ = scenes(script)
    if not scenes_:
        raise RuntimeError("Generated script contains no scenes")

    used = set()
    records = []
    fallback_count = 0

    for i, scene in enumerate(scenes_, 1):
        ts = terms(scene)
        queries = [
            " ".join(ts[:6]),
            " ".join(ts[:5]) + " photo",
            " ".join(ts[:4]) + " photography",
            " ".join(ts[:3]) + " documentary",
        ]
        candidates = []
        for q in queries:
            candidates += openverse(q) + commons(q)
        unique = {x["url"]: x for x in candidates}
        ranked = sorted(unique.values(), key=lambda x: score(x, ts), reverse=True)
        chosen = next((x for x in ranked if x["url"] not in used), None)

        if chosen is not None:
            try:
                path = download(chosen, i)
                used.add(chosen["url"])
                records.append((i, scene, path, chosen, score(chosen, ts)))
                print(f"Scene {i}: {chosen['source']} | score={score(chosen, ts)} | {chosen['title']}")
                continue
            except Exception as e:
                print(f"Scene {i}: external visual failed ({e}); using synthetic fallback")
        else:
            print(f"Scene {i}: no external visual available; using synthetic fallback")

        path = synthetic_visual(scene, i)
        fallback_count += 1
        fallback = {
            "url": "synthetic://scene-fallback",
            "title": f"Synthetic cinematic fallback for scene {i}",
            "desc": scene,
            "artist": "AI Video Automation",
            "license": "Generated by pipeline",
            "page": "",
            "w": 1080,
            "h": 1920,
            "source": "Synthetic fallback",
        }
        records.append((i, scene, path, fallback, 0))

    sources = []
    for i, scene, p, x, s in records:
        sources.append(f"Scene {i} | score={s} | {p.relative_to(ROOT)} | {x['title']} | {x['artist']} | {x['license']} | {x['page']} | {x['url']}")
    (VISUALS / "sources.txt").write_text("\n".join(sources), encoding="utf-8")
    print(f"VISUAL_REPORT external_images={len(records) - fallback_count} synthetic_fallbacks={fallback_count} scenes={len(scenes_)}")


if __name__ == "__main__":
    main()
