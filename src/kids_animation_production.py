from __future__ import annotations
import json, math, os, shutil, subprocess
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output" / "kids_animation"
ASSETS = OUTPUT / "assets"
SCENES = OUTPUT / "scenes"
FPS, WIDTH, HEIGHT, SCENE_SECONDS = 24, 1280, 720, 6

SCENES_DATA = [("bedroom", "Milo wakes up, stretches his paws and smiles at the golden sunrise."),("garden", "Milo trots through a colorful garden and waves to a butterfly."),("path", "Milo follows a winding path while little birds hop beside him."),("stream", "Milo carefully crosses a sparkling stream and laughs at a tiny splash."),("meadow", "Milo runs through a sunny meadow and watches the clouds drift by."),("flower", "Milo discovers a little drooping flower and notices that it needs help."),("water", "Milo gently waters the flower with a small blue watering can."),("magic", "The flower opens and bright sparkles dance around Milo."),("friends", "A rabbit, birds and butterflies arrive to celebrate with Milo."),("dance", "Milo and his friends dance together around the happy flower."),("sunset", "Milo sits beside the flower as the warm sunset fills the sky."),("goodbye", "Milo waves goodbye and walks home under friendly twinkling stars.")]
POEM_LINES = ["Wake up, Milo, morning is bright, stretch your paws in golden light.","Through the garden, off we go, where happy little flowers grow.","Follow the path and sing hello, with birds that flutter to and fro.","Across the stream, step by step, Milo laughs at every splash and pep.","In the meadow, soft winds play, clouds make pictures in the day.","Milo finds a little flower, drooping sadly hour by hour.","A little water, kind and slow, can help a tiny flower grow.","Look! The petals open wide, with golden sparkles by its side.","Friends arrive from everywhere, happy wings float through the air.","Dance together, laugh and sing, kindness makes the whole world ring.","As the sunset paints the sky, Milo watches fireflies fly.","Goodnight, friends, the day is through; a little kindness starts with you."]
STORY_LINES = ["Milo woke up early and saw the sun shining over his little home.","He stepped outside and followed a colorful garden path.","Along the way, friendly birds showed him where the path continued.","At the stream, Milo slowed down and crossed the stones carefully.","Soon he reached a meadow where the breeze made the flowers dance.","There he found a tiny flower with its head hanging low.","Milo brought some water and gently helped the little flower.","Slowly the flower opened its petals and seemed to smile.","Milo's friends came running when they saw what had happened.","Everyone celebrated because a little kindness had made a big difference.","As evening came, Milo rested beside his new flower friend.","Milo waved goodbye and promised to visit again tomorrow."]

def run(cmd: list[str]) -> None:
    if not cmd: raise ValueError("empty command")
    if cmd[0].startswith("-"): cmd.insert(0, "ffmpeg")
    if shutil.which(cmd[0]) is None: raise RuntimeError(f"Required executable not found: {cmd[0]}")
    subprocess.run(cmd, check=True, cwd=ROOT)

def make_background(kind: str, path: Path) -> None:
    img=Image.new("RGB",(WIDTH,HEIGHT),(180,220,250)); d=ImageDraw.Draw(img)
    if kind=="bedroom": img.paste((235,220,190),[0,0,WIDTH,HEIGHT]); d.rectangle([0,480,WIDTH,HEIGHT],fill=(215,190,150)); d.rectangle([120,260,520,480],fill=(120,160,205),outline=(70,100,145),width=8); d.ellipse([780,90,980,290],fill=(255,215,90))
    else:
        d.ellipse([980,65,1100,185],fill=(255,220,90)); d.polygon([(0,430),(260,300),(500,430),(760,285),(1280,430),(1280,720),(0,720)],fill=(145,195,115)); d.rectangle([0,510,WIDTH,HEIGHT],fill=(120,190,105))
        if kind in {"garden","flower","water","friends","dance"}:
            for x in range(100,1200,130): y=500+(x%90); d.line([x,y,x,y+55],fill=(45,125,55),width=6); d.ellipse([x-15,y-15,x+15,y+15],fill=(245,120,170))
        if kind=="stream": d.polygon([(520,720),(660,390),(760,390),(900,720)],fill=(80,175,225))
        if kind=="sunset": img.paste((235,155,110),[0,0,WIDTH,430]); d.ellipse([960,270,1100,410],fill=(255,205,95))
        if kind=="goodbye":
            img.paste((45,55,105),[0,0,WIDTH,430])
            for x,y in [(100,100),(240,170),(410,80),(610,145),(800,75),(1110,130)]: d.ellipse([x,y,x+7,y+7],fill=(255,240,170))
    img.save(path)

def make_character(path: Path) -> None:
    img=Image.new("RGBA",(420,420),(0,0,0,0)); d=ImageDraw.Draw(img); d.ellipse([35,80,145,245],fill=(145,92,48),outline=(95,60,35),width=6); d.ellipse([275,80,385,245],fill=(145,92,48),outline=(95,60,35),width=6); d.ellipse([100,230,320,405],fill=(185,125,65),outline=(105,70,40),width=7); d.ellipse([75,55,345,310],fill=(205,145,78),outline=(105,70,40),width=7); d.ellipse([145,175,275,265],fill=(238,190,125)); d.ellipse([196,178,225,205],fill=(45,35,30))
    for x in (145,250): d.ellipse([x,125,x+45,170],fill=(65,40,25)); d.ellipse([x+10,133,x+22,145],fill=(255,255,255))
    d.arc([175,195,250,245],0,180,fill=(75,45,35),width=6); d.polygon([(100,265),(320,265),(300,315),(120,315)],fill=(55,120,210)); d.polygon([(260,305),(325,305),(300,390),(255,350)],fill=(45,100,190)); img.save(path)

def make_flower(path: Path) -> None:
    img=Image.new("RGBA",(220,260),(0,0,0,0)); d=ImageDraw.Draw(img); d.line([110,110,110,245],fill=(50,135,65),width=12); d.ellipse([55,95,165,205],fill=(255,195,75),outline=(210,145,45),width=4)
    for a in range(0,360,72): r=math.radians(a); cx,cy=110+int(math.cos(r)*65),120+int(math.sin(r)*65); d.ellipse([cx-30,cy-30,cx+30,cy+30],fill=(245,105,170))
    img.save(path)

def assets(kind: str):
    ASSETS.mkdir(parents=True,exist_ok=True); bg=ASSETS/f"bg_{kind}.png"; char=ASSETS/"milo.png"; flower=ASSETS/"flower.png"
    if not bg.exists(): make_background(kind,bg)
    if not char.exists(): make_character(char)
    if not flower.exists(): make_flower(flower)
    return bg,char,flower

def voice(text: str, out: Path) -> None:
    if not shutil.which("espeak-ng"): raise RuntimeError("espeak-ng is required for the zero-cost local voice")
    run(["espeak-ng","-s","145","-p","55","-a","170","-w",str(out),text])

def scene(index: int, kind: str, line: str) -> Path:
    bg,char,flower=assets(kind); sd=SCENES/f"scene_{index:03d}"; sd.mkdir(parents=True,exist_ok=True); wav=sd/"voice.wav"; voice(line,wav); silent=sd/"silent.mp4"; out=sd/"scene.mp4"; sx,ex=((-80,930) if index%2 else (930,-80)); inputs=["-loop","1","-i",str(bg),"-loop","1","-i",str(char)]; flower_input=None
    if kind in {"flower","water","magic","friends","dance","sunset"}: inputs += ["-loop","1","-i",str(flower)]; flower_input=2
    audio_input=flower_input+1 if flower_input is not None else 2; inputs += ["-f","lavfi","-i",f"anullsrc=r=48000:cl=stereo:d={SCENE_SECONDS}"]
    if flower_input is not None: filt=f"[0:v]zoompan=z='min(zoom+0.0008,1.06)':d={FPS*SCENE_SECONDS}:s={WIDTH}x{HEIGHT}:fps={FPS}[bg];[1:v]format=rgba,scale=360:-1[m];[2:v]format=rgba,scale=180:-1[f];[bg][m]overlay=x='{sx}+({ex}-{sx})*(t/{SCENE_SECONDS})':y='390+12*sin(t*3)'[x];[x][f]overlay=x='900+15*sin(t*2)':y='390+8*sin(t*3)':enable='between(t,1.5,{SCENE_SECONDS})'[v]"
    else: filt=f"[0:v]zoompan=z='min(zoom+0.0008,1.06)':d={FPS*SCENE_SECONDS}:s={WIDTH}x{HEIGHT}:fps={FPS}[bg];[1:v]format=rgba,scale=360:-1[m];[bg][m]overlay=x='{sx}+({ex}-{sx})*(t/{SCENE_SECONDS})':y='390+12*sin(t*3)'[v]"
    run(inputs+["-filter_complex",filt,"-map","[v]","-map",f"{audio_input}:a","-t",str(SCENE_SECONDS),"-c:v","libx264","-preset","veryfast","-pix_fmt","yuv420p","-c:a","aac","-b:a","96k","-movflags","+faststart","-y",str(silent)])
    run(["-i",str(silent),"-i",str(wav),"-f","lavfi","-t",str(SCENE_SECONDS),"-i",f"sine=frequency={330+(index%4)*55}:sample_rate=48000:duration={SCENE_SECONDS}","-filter_complex","[2:a]volume=0.018[m];[1:a]apad=pad_dur=6,volume=1[n];[n][m]amix=inputs=2:duration=first[a]","-map","0:v","-map","[a]","-c:v","copy","-c:a","aac","-b:a","128k","-shortest","-y",str(out)])
    return out

def main() -> int:
    content=os.getenv("CONTENT_TYPE","poem").strip().lower(); topic=os.getenv("TOPIC","Milo and the Little Flower").strip(); duration=float(os.getenv("DURATION","1"))
    if content not in {"poem","story"}: raise RuntimeError("CONTENT_TYPE must be poem or story")
    if not topic: raise RuntimeError("TOPIC must not be empty")
    if not 1<=duration<=10: raise RuntimeError("DURATION must be between 1 and 10 minutes")
    OUTPUT.mkdir(parents=True,exist_ok=True); SCENES.mkdir(parents=True,exist_ok=True); count=max(1,math.ceil(duration*60/SCENE_SECONDS)); lines=POEM_LINES if content=="poem" else STORY_LINES
    clips=[scene(i+1,SCENES_DATA[i%len(SCENES_DATA)][0],lines[i%len(lines)]) for i in range(count)]
    concat=OUTPUT/"concat.txt"; concat.write_text("\n".join(f"file '{p.resolve()}'" for p in clips)+"\n",encoding="utf-8"); final=OUTPUT/"kids-animation.mp4"
    run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(concat),"-c","copy","-movflags","+faststart",str(final)])
    if not final.is_file() or final.stat().st_size<100000: raise RuntimeError("Final animation was not created or is unexpectedly small")
    production={"topic":topic,"content_type":content,"duration_minutes":duration,"duration_seconds":duration*60,"video":"kids-animation.mp4","size_bytes":final.stat().st_size,"production_mode":"zero_cost_local","voice":"espeak-ng","renderer":"ffmpeg","scene_count":count}
    (OUTPUT/"production.json").write_text(json.dumps(production,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(f"Created {final} ({final.stat().st_size} bytes)"); return 0

if __name__ == "__main__": raise SystemExit(main())
