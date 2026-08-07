import html
import re
import time
from pathlib import Path
from urllib.parse import quote
import requests

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
VISUALS = ROOT / "assets" / "visuals"
VISUALS.mkdir(parents=True, exist_ok=True)
OPENVERSE = "https://api.openverse.org/v1/images/"
COMMONS = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "AI-Video-Automation/4.0"}
STOP = set("about after again because before could every first from have into more most never only other over really their there these this those through what when where which while with would your that than they them then were will also some many fact facts interesting people thing story stories history video videos footage of the and are was for not you but has had its our their documentary image images clip clips scene scenes".split())


def clean(v):
    return re.sub(r"\s+", " ", html.unescape(re.sub("<.*?>", " ", str(v or "")))).strip()


def get(url, params, attempts=4):
    for i in range(attempts):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=30)
            if r.status_code == 429:
                time.sleep(min(60, 4 * (2 ** i)))
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if i == attempts - 1:
                print(f"Search failed: {e}")
                return {}
            time.sleep(min(20, 2 * (2 ** i)))
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
        try: w, h = int(x.get("width") or 0), int(x.get("height") or 0)
        except Exception: w, h = 0, 0
        if w < 640 or h < 360:
            continue
        tags = []
        for t in x.get("tags") or []:
            if isinstance(t, str): tags.append(t)
            elif isinstance(t, dict):
                for k in ("name", "title", "tag", "label"):
                    if isinstance(t.get(k), str): tags.append(t[k]); break
        out.append({"url":url,"title":clean(x.get("title",q)),"desc":clean(" ".join(tags)),"artist":clean(x.get("creator")),"license":clean(x.get("license")),"page":x.get("foreign_landing_url") or x.get("detail_url", ""),"w":w,"h":h,"source":"Openverse"})
    return out


def commons(q):
    data = get(COMMONS, {"action":"query","format":"json","generator":"search","gsrsearch":q,"gsrnamespace":6,"gsrlimit":15,"prop":"imageinfo|info","iiprop":"url|mime|width|height|extmetadata","inprop":"url"})
    out=[]
    for p in data.get("query",{}).get("pages",{}).values():
        info=p.get("imageinfo",[{}])[0]; url=info.get("url"); mime=info.get("mime","")
        if not url or not mime.startswith("image/"): continue
        try: w,h=int(info.get("width") or 0),int(info.get("height") or 0)
        except Exception: w,h=0,0
        if w < 640 or h < 360: continue
        meta=info.get("extmetadata",{})
        out.append({"url":url,"title":clean(meta.get("ObjectName",{}).get("value",p.get("title",q))),"desc":clean(meta.get("ImageDescription",{}).get("value","")),"artist":clean(meta.get("Artist",{}).get("value","")),"license":clean(meta.get("LicenseShortName",{}).get("value","")),"page":p.get("fullurl",f"https://commons.wikimedia.org/wiki/{quote(p.get('title',''))}"),"w":w,"h":h,"source":"Wikimedia Commons"})
    return out


def score(x, ts):
    text=(x["title"]+" "+x["desc"]).lower(); s=0
    for t in ts:
        if t in x["title"].lower(): s += 20
        elif t in text: s += 7
    if x["w"]*x["h"] >= 1920*1080: s += 10
    elif x["w"]*x["h"] >= 1280*720: s += 5
    return s


def download(x, n):
    r=requests.get(x["url"],headers=UA,timeout=90,stream=True); r.raise_for_status()
    path=VISUALS/f"visual_{n:02d}.jpg"; total=0
    with path.open("wb") as f:
        for chunk in r.iter_content(1024*1024):
            if chunk: f.write(chunk); total += len(chunk)
            if total > 120*1024*1024: raise RuntimeError("visual too large")
    if total < 30000: path.unlink(missing_ok=True); raise RuntimeError("visual too small")
    return path


def main():
    script=(OUTPUT/"script.txt").read_text(encoding="utf-8").strip()
    for p in VISUALS.glob("visual_*"): p.unlink()
    scenes_=scenes(script); used=set(); records=[]
    for i,scene in enumerate(scenes_,1):
        ts=terms(scene)
        queries=[" ".join(ts[:6])," ".join(ts[:5])+" photo"," ".join(ts[:4])+" photography"," ".join(ts[:3])+" documentary"]
        candidates=[]
        for q in queries:
            candidates += openverse(q) + commons(q)
        unique={x["url"]:x for x in candidates}
        ranked=sorted(unique.values(),key=lambda x:score(x,ts),reverse=True)
        chosen=next((x for x in ranked if x["url"] not in used),None)
        if chosen is None:
            print(f"Scene {i}: no external visual available")
            continue
        try:
            path=download(chosen,len(records)); used.add(chosen["url"])
            records.append((i,scene,path,chosen,score(chosen,ts)))
            print(f"Scene {i}: {chosen['source']} | score={score(chosen,ts)} | {chosen['title']}")
        except Exception as e:
            print(f"Scene {i}: download failed: {e}")
    if not records:
        raise RuntimeError("No public visuals could be downloaded")
    (VISUALS/"sources.txt").write_text("\n".join(f"Scene {i} | score={s} | {p.relative_to(ROOT)} | {x['title']} | {x['artist']} | {x['license']} | {x['page']} | {x['url']}" for i,scene,p,x,s in records),encoding="utf-8")
    print(f"VISUAL_REPORT external_images={len(records)} scenes={len(scenes_)}")

if __name__ == "__main__": main()
