from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import wave
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output" / "kids_animation"
SCENES_DIR = OUTPUT / "scenes"
ASSET_DIR = OUTPUT / "assets"
FPS = 24
W, H = 960, 540
SCENE_SECONDS = 6

EPISODE = [
    ("bedroom", "Milo wakes up, rubs his sleepy eyes, opens the curtains, and notices a tiny glowing light outside."),
    ("garden", "Milo opens the door and skips into the garden. Lumi the little firefly circles around his nose."),
    ("path", "Lumi flies down the path. Milo follows while leaves swirl and three birds hop along beside him."),
    ("stream", "Milo reaches a sparkling stream and crosses three stepping stones. He slips, splashes, and laughs."),
    ("meadow", "In the meadow Milo hears a tiny cry and discovers a thirsty flower with its petals closed."),
    ("help", "Milo kneels beside the flower, smiles kindly, and carries over his little blue watering can."),
    ("water", "Milo gently waters the flower. The leaves lift and the flower begins to wake up."),
    ("magic", "The flower opens wide and golden sparkles float into the air as Lumi dances around it."),
    ("friends", "A rabbit and three birds arrive. Milo waves and everyone gathers around the glowing flower."),
    ("dance", "Milo, Lumi, the rabbit, and the birds dance together in a joyful circle."),
    ("sunset", "The sun sets behind the hills. Milo sits beside the flower and smiles at his friends."),
    ("night", "Milo waves goodnight. Lumi lights the path home while stars twinkle above the quiet garden."),
]

POEM = [
    "Wake up, Milo, morning is bright! Stretch your paws in golden light!",
    "Skip through the garden, green and wide. Little Lumi dances by your side!",
    "Follow the path and sing hello. Watch the happy leaves all blow!",
    "Hop on the stones, splash in the stream. Every little adventure is a dream!",
    "In the meadow, what do we see? A sleepy flower waiting patiently.",
    "Kind little Milo kneels down low. A gentle helping hand can make things grow.",
    "Tip the can and water slow. Tiny drops help flowers grow!",
    "Open, open, petals bright. Golden sparkles fill the light!",
    "Friends come hopping, friends come flying. Happy little hearts, no one is hiding!",
    "Clap your paws and dance around. Kindness makes a happy sound!",
    "When the sun sinks soft and low, Milo sees how kindness grows.",
    "Goodnight, friends, the stars shine through. Tomorrow brings adventures new!",
]

STORY = [
    "Milo woke with a sleepy yawn. A tiny glow twinkled outside his window.",
    "He opened the door and met Lumi, a friendly little firefly with a warm golden light.",
    "Lumi flew down the garden path, and Milo followed with three cheerful birds.",
    "At the stream Milo crossed the stones. Splash! He nearly slipped, then laughed.",
    "Across the stream he heard a tiny cry. A little flower was thirsty and its petals were closed.",
    "Milo knelt beside the flower and promised to help. He hurried for his watering can.",
    "Drop by drop, Milo watered the flower. Slowly its leaves lifted toward the sun.",
    "The flower opened with a sparkle. Lumi danced around it like a tiny star.",
    "A rabbit and the birds arrived. Everyone gathered to see the beautiful flower.",
    "They danced together because kindness had brought them all to the same place.",
    "At sunset Milo rested beside the flower and smiled at his new friends.",
    "Milo waved goodnight. Lumi lit the path home, and tomorrow another adventure would begin.",
]


def cmd(args: list[str]) -> None:
    if not args:
        raise ValueError("empty command")
    if args[0].startswith("-"):
        args.insert(0, "ffmpeg")
    if not shutil.which(args[0]):
        raise RuntimeError(f"Required executable not found: {args[0]}")
    subprocess.run(args, cwd=ROOT, check=True)


def font(size: int):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"):
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def background(kind: str, t: float) -> Image.Image:
    im = Image.new("RGB", (W, H), (150, 210, 250))
    d = ImageDraw.Draw(im)
    if kind == "bedroom":
        d.rectangle((0, 0, W, H), fill=(246, 226, 190)); d.rectangle((0, 390, W, H), fill=(205, 170, 130))
        d.rectangle((70, 215, 380, 390), fill=(85, 135, 195), outline=(55, 85, 125), width=6)
        d.rectangle((610, 80, 850, 275), fill=(165, 210, 245), outline=(110, 150, 185), width=6)
        d.ellipse((690, 105, 790, 205), fill=(255, 220, 95))
        d.rectangle((585, 275, 875, 390), fill=(238, 230, 212))
        return im
    sky = (150, 210, 250) if kind not in {"sunset", "night"} else ((235, 155, 120) if kind == "sunset" else (45, 58, 110))
    d.rectangle((0, 0, W, 330), fill=sky)
    if kind == "night":
        for x, y in [(90, 70), (210, 130), (350, 55), (500, 115), (700, 65), (850, 150)]: d.ellipse((x, y, x+6, y+6), fill=(255, 244, 180))
    else:
        sun_y = 65 if kind != "sunset" else 220
        d.ellipse((770, sun_y, 900, sun_y+130), fill=(255, 220, 95))
    d.polygon([(0, 350), (180, 250), (350, 350), (520, 240), (960, 350), (960, 540), (0, 540)], fill=(125, 185, 105))
    d.rectangle((0, 410, W, H), fill=(95, 170, 95))
    for x, y, s in [(55, 260, 1.0), (820, 260, 1.2), (300, 300, .75)]:
        d.rectangle((x-9, y, x+9, y+115), fill=(105, 72, 42))
        d.ellipse((x-65*s, y-55*s, x+65*s, y+40*s), fill=(65, 145, 75))
    if kind == "path": d.polygon([(470, 540), (505, 350), (555, 350), (650, 540)], fill=(205, 170, 120))
    if kind == "stream":
        d.polygon([(360, 540), (450, 330), (535, 330), (650, 540)], fill=(70, 170, 225))
        for x in (410, 485, 560): d.ellipse((x, 430, x+62, 458), fill=(180, 175, 165))
    if kind in {"meadow", "help", "water", "magic", "friends", "dance", "sunset"}:
        for x in range(35, 930, 80):
            y = 405 + ((x * 13) % 60); d.line((x, y, x, y+28), fill=(45, 125, 55), width=3)
            d.ellipse((x-8, y-8, x+8, y+8), fill=(245, 125, 175)); d.ellipse((x-3, y-3, x+3, y+3), fill=(255, 215, 75))
    if kind in {"meadow", "help", "water", "magic", "friends", "dance", "sunset"}:
        # recurring flower landmark
        d.line((760, 375, 760, 485), fill=(45, 130, 60), width=7)
        petals = (245, 105, 175) if kind != "magic" else (255, 185, 75)
        for a in range(0, 360, 72):
            r = math.radians(a); cx = 760 + int(math.cos(r)*38); cy = 360 + int(math.sin(r)*38)
            d.ellipse((cx-20, cy-20, cx+20, cy+20), fill=petals)
        d.ellipse((740, 340, 780, 380), fill=(255, 205, 70))
    return im


def draw_milo(im: Image.Image, x: float, y: float, scale: float, action: str, t: float) -> None:
    d = ImageDraw.Draw(im, "RGBA")
    s = scale; bounce = 5 * math.sin(t * math.pi * 2) if action in {"walk", "dance", "excited"} else 0
    x, y = x, y + bounce
    # soft shadow
    d.ellipse((x-55*s, y+105*s, x+55*s, y+125*s), fill=(35, 70, 45, 70))
    # legs with alternating stride
    stride = 20*s*math.sin(t*math.pi*4) if action in {"walk", "run", "dance"} else 0
    d.rounded_rectangle((x-48*s, y+55*s, x-18*s, y+120*s), radius=int(12*s), fill=(45, 95, 175, 255))
    d.rounded_rectangle((x+18*s, y+55*s+stride, x+48*s, y+120*s+stride), radius=int(12*s), fill=(35, 82, 160, 255))
    # body and shirt
    d.ellipse((x-82*s, y-5*s, x+82*s, y+105*s), fill=(185, 125, 65, 255), outline=(100, 65, 40, 255), width=max(2, int(4*s)))
    d.pieslice((x-78*s, y+25*s, x+78*s, y+125*s), 0, 180, fill=(55, 120, 210, 255))
    # ears/head
    d.ellipse((x-95*s, y-125*s, x-20*s, y-15*s), fill=(145, 92, 48, 255), outline=(95, 60, 35, 255), width=max(2, int(4*s)))
    d.ellipse((x+20*s, y-125*s, x+95*s, y-15*s), fill=(145, 92, 48, 255), outline=(95, 60, 35, 255), width=max(2, int(4*s)))
    d.ellipse((x-88*s, y-145*s, x+88*s, y+25*s), fill=(205, 145, 78, 255), outline=(105, 70, 40, 255), width=max(2, int(4*s)))
    # eyes blink periodically
    blink = (t % 3.7) > 3.48
    if blink:
        d.line((x-48*s, y-75*s, x-20*s, y-75*s), fill=(45, 35, 30, 255), width=max(2, int(5*s)))
        d.line((x+20*s, y-75*s, x+48*s, y-75*s), fill=(45, 35, 30, 255), width=max(2, int(5*s)))
    else:
        for ex in (-35, 35):
            d.ellipse((x+(ex-13)*s, y-90*s, x+(ex+13)*s, y-64*s), fill=(45, 35, 30, 255)); d.ellipse((x+(ex-7)*s, y-85*s, x+(ex+2)*s, y-76*s), fill="white")
    # expressive mouth
    mouth = 6 + 10*abs(math.sin(t*math.pi*5)) if action in {"talk", "excited", "laugh"} else 5
    d.ellipse((x-18*s, y-42*s, x+18*s, y+(-42+mouth)*s), fill=(80, 40, 45, 255))
    # arms: wave/dance/talk
    arm = 28*math.sin(t*math.pi*2) if action in {"wave", "dance"} else 0
    d.line((x-62*s, y+30*s, x-105*s, y+70*s-arm*s/2), fill=(185,125,65,255), width=max(5,int(13*s)))
    d.line((x+62*s, y+30*s, x+105*s, y+70*s+arm*s/2), fill=(185,125,65,255), width=max(5,int(13*s)))


def draw_lumi(im: Image.Image, x: float, y: float, t: float) -> None:
    d = ImageDraw.Draw(im, "RGBA"); pulse = 1 + .15*math.sin(t*math.pi*4)
    for r,a in [(28,25),(20,45),(13,180)]: d.ellipse((x-r*pulse,y-r*pulse,x+r*pulse,y+r*pulse), fill=(255,220,90,a))
    d.ellipse((x-7,y-7,x+7,y+7), fill=(255,235,120,255))


def draw_rabbit(im: Image.Image, x: float, y: float, t: float) -> None:
    d=ImageDraw.Draw(im,"RGBA"); hop=7*abs(math.sin(t*math.pi*2)); y-=hop
    d.ellipse((x-38,y-15,x+38,y+48),fill=(235,235,225,255),outline=(130,130,125,255),width=3)
    d.ellipse((x-30,y-60,x-8,y-10),fill=(235,235,225,255),outline=(130,130,125,255),width=3); d.ellipse((x+8,y-60,x+30,y-10),fill=(235,235,225,255),outline=(130,130,125,255),width=3)
    d.ellipse((x-15,y+2,x-7,y+10),fill=(40,40,40,255)); d.ellipse((x+7,y+2,x+15,y+10),fill=(40,40,40,255)); d.ellipse((x-5,y+15,x+5,y+23),fill=(245,145,160,255))


def draw_birds(im: Image.Image, t: float) -> None:
    d=ImageDraw.Draw(im,"RGBA")
    for i,(bx,by) in enumerate(((150,170),(210,205),(265,155))):
        wing=12*math.sin(t*math.pi*5+i)
        d.arc((bx-22,by-wing,bx,by+20),180,350,fill=(55,80,120,255),width=4); d.arc((bx,by-wing,bx+22,by+20),190,360,fill=(55,80,120,255),width=4)


def render_scene(kind: str, scene_index: int, seconds: float, out: Path) -> None:
    frames = int(round(seconds*FPS)); raw = out.with_suffix('.frames.mp4')
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    writer = ["ffmpeg","-y","-f","rawvideo","-pix_fmt","rgb24","-s",f"{W}x{H}","-r",str(FPS),"-i","-","-an","-c:v","libx264","-preset","veryfast","-crf","20","-pix_fmt","yuv420p",str(raw)]
    proc=subprocess.Popen(writer,cwd=ROOT,stdin=subprocess.PIPE)
    assert proc.stdin is not None
    for n in range(frames):
        t=n/FPS; im=background(kind,t)
        phase=t/seconds
        if kind == "bedroom": mx=180+80*ease(min(1,phase*2)); my=315; act="talk"
        elif kind == "stream": mx=240+420*ease(phase); my=310; act="run"
        elif kind == "dance": mx=470+70*math.sin(t*math.pi*2); my=320; act="dance"
        elif kind in {"sunset","night"}: mx=520; my=325; act="wave" if kind=="night" else "idle"
        else: mx=170+420*ease(phase); my=330; act="walk" if kind in {"garden","path","friends"} else "talk"
        draw_milo(im,mx,my,0.95,act,t)
        if kind in {"garden","path","stream","meadow","help","water","magic","friends","dance"}:
            lx=260+400*phase; ly=150+35*math.sin(t*math.pi*2); draw_lumi(im,lx,ly,t)
        if kind in {"path","friends","dance"}: draw_birds(im,t)
        if kind in {"friends","dance"}: draw_rabbit(im,700,350,t)
        if kind == "magic":
            d=ImageDraw.Draw(im,"RGBA")
            for k in range(12):
                a=t*1.7+k*.52; x=760+75*math.cos(a)*(0.5+phase); y=350-100*phase+55*math.sin(a*1.7); d.ellipse((x-4,y-4,x+4,y+4),fill=(255,220,95,210))
        if kind == "water":
            d=ImageDraw.Draw(im,"RGBA"); d.rounded_rectangle((600,365,675,430),radius=15,fill=(60,135,225,255)); d.ellipse((655,360,700,420),outline=(60,135,225,255),width=9); d.line((680,410,755,405),fill=(90,170,235,210),width=7)
        proc.stdin.write(im.tobytes())
    proc.stdin.close(); rc=proc.wait()
    if rc: raise RuntimeError(f"ffmpeg frame render failed with exit code {rc}")
    cmd(["ffmpeg","-y","-i",str(raw),"-c","copy",str(out)])
    raw.unlink(missing_ok=True)


def piper_voice(text: str, out: Path) -> None:
    piper = shutil.which("piper")
    model = os.environ.get("PIPER_MODEL", str(ROOT/"voices"/"en_US-lessac-medium.onnx"))
    if not piper or not Path(model).exists():
        raise RuntimeError("Piper voice is not installed. The workflow must install the pinned local voice model before production.")
    subprocess.run([piper,"--model",model,"--output_file",str(out),"--sentence-silence","0.18"],input=text,text=True,cwd=ROOT,check=True)


def tone_wav(out: Path, notes: Iterable[tuple[float,float]], duration: float) -> None:
    rate=22050; samples=int(rate*duration); data=[]
    notes=list(notes)
    for i in range(samples):
        t=i/rate; value=0.0
        for start,freq,length,amp in notes:
            if start<=t<start+length:
                local=t-start; env=min(1,local/.04,max(0,(start+length-t)/.12)); value += amp*env*math.sin(2*math.pi*freq*local)
        data.append(max(-1,min(1,value)))
    pcm=b''.join(int(v*26000).to_bytes(2,'little',signed=True) for v in data)
    with wave.open(str(out),'wb') as wf: wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(rate); wf.writeframes(pcm)


def mix_scene(video: Path, voice_file: Path, scene_index: int, out: Path) -> None:
    music=voice_file.with_name('music.wav'); dur=SCENE_SECONDS
    roots=[261.63,329.63,392.0,523.25]
    notes=[]
    for k in range(0, int(dur), 1): notes.append((k, roots[(k+scene_index)%4], .8, .055))
    tone_wav(music,notes,dur)
    cmd(["ffmpeg","-y","-i",str(video),"-i",str(voice_file),"-i",str(music),"-filter_complex","[1:a]loudnorm=I=-16:LRA=7:TP=-1.5[voice];[2:a]volume=0.22[music];[voice][music]amix=inputs=2:duration=first:dropout_transition=1[a]","-map","0:v","-map","[a]","-c:v","copy","-c:a","aac","-b:a","128k","-shortest",str(out)])


def main() -> int:
    content=os.getenv('CONTENT_TYPE','poem').strip().lower(); topic=os.getenv('TOPIC','Milo and the Little Flower').strip(); duration=float(os.getenv('DURATION','1'))
    if content not in {'poem','story'}: raise RuntimeError('CONTENT_TYPE must be poem or story')
    if not topic: raise RuntimeError('TOPIC must not be empty')
    if not 1<=duration<=10: raise RuntimeError('DURATION must be between 1 and 10 minutes')
    OUTPUT.mkdir(parents=True,exist_ok=True); SCENES_DIR.mkdir(parents=True,exist_ok=True)
    lines=POEM if content=='poem' else STORY; count=max(1,math.ceil(duration*60/SCENE_SECONDS)); clips=[]
    for i in range(count):
        kind,_=EPISODE[i%len(EPISODE)]; sd=SCENES_DIR/f'scene_{i+1:03d}'; sd.mkdir(parents=True,exist_ok=True)
        silent=sd/'animation.mp4'; voice_file=sd/'voice.wav'; final_scene=sd/'scene.mp4'
        render_scene(kind,i+1,SCENE_SECONDS,silent); piper_voice(lines[i%len(lines)],voice_file); mix_scene(silent,voice_file,i+1,final_scene); clips.append(final_scene)
    concat=OUTPUT/'concat.txt'; concat.write_text('\n'.join(f"file '{p.resolve()}'" for p in clips)+'\n',encoding='utf-8')
    final=OUTPUT/'kids-animation.mp4'; cmd(['ffmpeg','-y','-f','concat','-safe','0','-i',str(concat),'-c','copy','-movflags','+faststart',str(final)])
    if not final.is_file() or final.stat().st_size<100000: raise RuntimeError('Final video missing or too small')
    meta={'topic':topic,'content_type':content,'duration_minutes':duration,'video':'kids-animation.mp4','size_bytes':final.stat().st_size,'renderer':'scene_based_2d_cartoon','voice':'piper_en_US_lessac_medium','music':'procedural_original','scene_count':count,'cost':'$0'}
    (OUTPUT/'production.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(meta,indent=2)); return 0

if __name__=='__main__': raise SystemExit(main())
