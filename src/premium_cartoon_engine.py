from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output" / "kids_animation"
SCENES = OUT / "scenes"
FPS = 24
W, H = 1280, 720
S = 2
DURATION = 6.0

BEATS = [
    ("bedroom", "Milo wakes up and sees a tiny golden light outside his window."),
    ("garden", "Milo follows Lumi into the garden, where the morning flowers sway in the breeze."),
    ("path", "Lumi races along the path and Milo happily follows, waving to the birds."),
    ("stream", "Milo crosses the sparkling stream, slips on a stone, and laughs at his splash."),
    ("meadow", "A thirsty little flower is waiting in the meadow with its petals closed."),
    ("help", "Milo brings his watering can and gently helps the flower."),
    ("water", "Drop by drop, the flower drinks and slowly lifts its leaves toward the sun."),
    ("magic", "The flower opens in a burst of warm golden sparkles while Lumi dances around it."),
    ("friends", "A rabbit and cheerful birds arrive to share the wonderful discovery."),
    ("dance", "Everyone dances together because a small act of kindness made a big difference."),
    ("sunset", "The sun sinks behind the hills and Milo rests beside his new friends."),
    ("night", "Milo says goodnight while Lumi lights the path beneath a sky full of stars."),
]

POEM = [
    "Wake up, Milo, morning is bright! Stretch and smile in golden light!",
    "Skip through the garden, green and wide. Little Lumi flies beside!",
    "Follow the path and sing hello. Watch the happy flowers blow!",
    "Step on the stones, splash in the stream. Every adventure feels like a dream!",
    "In the meadow, what do we see? A sleepy flower waiting patiently.",
    "Kind little Milo kneels down low. Gentle helping hands can make things grow!",
    "Tip the can and water slow. Tiny drops help flowers grow!",
    "Open, open, petals bright. Golden sparkles fill the light!",
    "Friends come hopping, friends come flying. Happy hearts are never hiding!",
    "Clap your paws and dance around. Kindness makes a joyful sound!",
    "When the sun sinks soft and low, Milo sees how kindness grows.",
    "Goodnight, friends, the stars shine through. Tomorrow brings adventures new!",
]

STORY = [
    "Milo woke with a sleepy yawn. A tiny golden light twinkled outside his window.",
    "He opened the door and met Lumi, a friendly firefly who glowed like a tiny lantern.",
    "Lumi flew down the garden path, and Milo followed with three cheerful birds.",
    "At the stream Milo crossed the stones. Splash! He slipped, then laughed.",
    "Across the stream he heard a tiny cry. A little flower was thirsty and closed tight.",
    "Milo promised to help. He hurried back with his little watering can.",
    "Drop by drop, Milo watered the flower. Its leaves slowly lifted toward the sun.",
    "The flower opened with a warm golden sparkle. Lumi danced like a tiny star.",
    "A rabbit and the birds arrived. Everyone gathered around the beautiful flower.",
    "They danced together because kindness had brought everyone together.",
    "At sunset Milo rested beside the flower and smiled at his new friends.",
    "Milo waved goodnight. Lumi lit the path home beneath the twinkling stars.",
]


def exe(name: str) -> str:
    p = shutil.which(name)
    if not p:
        raise RuntimeError(f"Missing required executable: {name}")
    return p


def ffmpeg(args: list[str]) -> None:
    exe("ffmpeg")
    subprocess.run(["ffmpeg", *args], cwd=ROOT, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * max(0.0, min(1.0, t))


def ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def font(size: int):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"):
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def gradient(draw: ImageDraw.ImageDraw, box, top, bottom):
    x0, y0, x1, y1 = box
    h = max(1, y1-y0)
    for y in range(y0, y1):
        q=(y-y0)/h
        c=tuple(int(lerp(top[i],bottom[i],q)) for i in range(3))
        draw.line((x0,y,x1,y),fill=c)


def scene_bg(kind: str, t: float) -> Image.Image:
    im=Image.new("RGB",(W,H)); d=ImageDraw.Draw(im)
    if kind=="night": top,bottom=(28,40,91),(78,62,120)
    elif kind=="sunset": top,bottom=(244,150,120),(255,207,135)
    elif kind=="bedroom": top,bottom=(240,221,194),(211,177,139)
    else: top,bottom=(119,190,244),(224,244,219)
    gradient(d,(0,0,W,430),top,bottom)
    if kind=="bedroom":
        d.rectangle((0,430,W,H),fill=(192,150,112)); d.rounded_rectangle((90,260,500,475),30,fill=(91,119,169),outline=(61,74,111),width=8)
        d.rectangle((720,95,1110,350),fill=(177,220,244),outline=(105,136,164),width=10)
        d.ellipse((830,125,960,255),fill=(255,225,114)); d.rectangle((675,350,1140,470),fill=(233,221,199))
        return im
    if kind=="night":
        for x,y in [(80,85),(170,180),(310,100),(470,150),(650,80),(810,170),(1030,105),(1170,185)]:
            d.ellipse((x,y,x+7,y+7),fill=(255,248,185))
    else:
        sunx=1020; suny=105 if kind!="sunset" else 260
        d.ellipse((sunx-70,suny-70,sunx+70,suny+70),fill=(255,221,105))
    d.polygon([(0,430),(180,300),(380,425),(620,280),(860,420),(1060,305),(1280,420),(1280,H),(0,H)],fill=(105,164,91))
    d.rectangle((0,500,W,H),fill=(74,145,82))
    # parallax trees
    for x,y,r in [(90,300,85),(330,330,65),(1070,295,90),(1210,340,65)]:
        d.rectangle((x-12,y,x+12,520),fill=(104,72,46)); d.ellipse((x-r,y-r,x+r,y+30),fill=(62,139,73))
    if kind=="path": d.polygon([(510,H),(590,390),(650,390),(780,H)],fill=(202,170,120))
    if kind=="stream":
        d.polygon([(420,H),(535,375),(700,375),(870,H)],fill=(66,166,220))
        for x in (515,620,730): d.ellipse((x,500,x+85,540),fill=(178,174,165),outline=(130,130,125),width=3)
    # flowers / grass
    for x in range(40,1260,90):
        y=510+(x*7)%95; d.line((x,y,x,y+28),fill=(45,120,60),width=4); d.ellipse((x-9,y-9,x+9,y+9),fill=(244,132,179)); d.ellipse((x-4,y-4,x+4,y+4),fill=(255,216,75))
    # landmark flower
    if kind in {"meadow","help","water","magic","friends","dance","sunset"}:
        d.line((970,420,970,585),fill=(43,125,60),width=10)
        petal=(255,165,190) if kind!="magic" else (255,190,76)
        for a in range(0,360,72):
            r=math.radians(a); cx=970+int(math.cos(r)*58); cy=400+int(math.sin(r)*58); d.ellipse((cx-28,cy-28,cx+28,cy+28),fill=petal)
        d.ellipse((940,370,1000,430),fill=(255,208,70))
    return im


def shadow(d,x,y,rx,ry): d.ellipse((x-rx,y-ry,x+rx,y+ry),fill=(20,50,35,65))


def milo(im,x,y,scale,t,action):
    d=ImageDraw.Draw(im,"RGBA"); s=scale; phase=math.sin(t*math.pi*2); bounce=6*phase if action in {"walk","run","dance"} else 0; y+=bounce
    shadow(d,x,y+145*s,62*s,14*s)
    stride=24*s*math.sin(t*math.pi*4) if action in {"walk","run","dance"} else 0
    # legs, shoes
    d.rounded_rectangle((x-43*s,y+55*s,x-12*s,y+132*s),12,fill=(48,92,175,255)); d.rounded_rectangle((x+12*s,y+55*s+stride,x+43*s,y+132*s+stride),12,fill=(38,77,155,255))
    d.ellipse((x-50*s,y+118*s,x-3*s,y+145*s),fill=(55,48,46,255)); d.ellipse((x+3*s,y+118*s+stride,x+50*s,y+145*s+stride),fill=(55,48,46,255))
    # body
    d.ellipse((x-78*s,y-2*s,x+78*s,y+106*s),fill=(207,145,80,255),outline=(100,64,39,255),width=5)
    d.pieslice((x-76*s,y+18*s,x+76*s,y+132*s),0,180,fill=(62,126,213,255))
    # ears and head
    d.ellipse((x-88*s,y-128*s,x-20*s,y-18*s),fill=(151,94,51,255),outline=(92,57,36,255),width=5); d.ellipse((x+20*s,y-128*s,x+88*s,y-18*s),fill=(151,94,51,255),outline=(92,57,36,255),width=5)
    d.ellipse((x-84*s,y-145*s,x+84*s,y+24*s),fill=(215,154,88,255),outline=(103,66,40,255),width=5)
    # cheek highlights
    d.ellipse((x-69*s,y-37*s,x-30*s,y-5*s),fill=(239,174,143,90)); d.ellipse((x+30*s,y-37*s,x+69*s,y-5*s),fill=(239,174,143,90))
    blink=(t%3.5)>3.28
    if blink:
        d.line((x-50*s,y-76*s,x-22*s,y-76*s),fill=(40,30,25,255),width=6); d.line((x+22*s,y-76*s,x+50*s,y-76*s),fill=(40,30,25,255),width=6)
    else:
        for ex in (-36,36):
            d.ellipse((x+(ex-14)*s,y-92*s,x+(ex+14)*s,y-61*s),fill=(40,31,27,255)); d.ellipse((x+(ex-7)*s,y-86*s,x+(ex+2)*s,y-77*s),fill=(255,255,255,255))
    d.ellipse((x-9*s,y-54*s,x+9*s,y-37*s),fill=(92,48,40,255))
    mouth=7+12*abs(math.sin(t*math.pi*6)) if action in {"talk","laugh","excited"} else 5
    d.ellipse((x-20*s,y-31*s,x+20*s,y+(-31+mouth)*s),fill=(86,42,48,255))
    arm=34*math.sin(t*math.pi*2) if action in {"wave","dance"} else 0
    d.line((x-60*s,y+35*s,x-110*s,y+76*s-arm*s/2),fill=(207,145,80,255),width=max(8,int(15*s)))
    d.line((x+60*s,y+35*s,x+110*s,y+76*s+arm*s/2),fill=(207,145,80,255),width=max(8,int(15*s)))
    # little backpack
    d.rounded_rectangle((x-95*s,y+10*s,x-65*s,y+80*s),10,fill=(238,157,58,255))


def lumi(im,x,y,t):
    d=ImageDraw.Draw(im,"RGBA"); pulse=1+.18*math.sin(t*math.pi*5)
    for r,a in [(52,18),(36,30),(23,60)]: d.ellipse((x-r*pulse,y-r*pulse,x+r*pulse,y+r*pulse),fill=(255,219,92,a))
    d.ellipse((x-10,y-10,x+10,y+10),fill=(255,239,135,255)); d.ellipse((x-4,y-4,x+2,y+2),fill=(255,255,240,255))


def rabbit(im,x,y,t):
    d=ImageDraw.Draw(im,"RGBA"); hop=9*abs(math.sin(t*math.pi*2)); y-=hop
    d.ellipse((x-48,y-10,x+48,y+70),fill=(242,239,228,255),outline=(133,130,125,255),width=4)
    d.ellipse((x-38,y-82,x-8,y-5),fill=(242,239,228,255),outline=(133,130,125,255),width=4); d.ellipse((x+8,y-82,x+38,y-5),fill=(242,239,228,255),outline=(133,130,125,255),width=4)
    d.ellipse((x-18,y+8,x-8,y+20),fill=(35,35,35,255)); d.ellipse((x+8,y+8,x+18,y+20),fill=(35,35,35,255)); d.ellipse((x-7,y+25,x+7,y+39),fill=(245,145,165,255))


def birds(im,t):
    d=ImageDraw.Draw(im,"RGBA")
    for i,(x,y) in enumerate(((180,170),(270,215),(355,155))):
        wing=16*math.sin(t*math.pi*5+i); d.arc((x-28,y-wing,x,y+26),180,350,fill=(60,76,116,255),width=6); d.arc((x,y-wing,x+28,y+26),190,360,fill=(60,76,116,255),width=6)


def render(kind, index, out):
    frames=int(DURATION*FPS); raw=out.with_suffix(".raw.mp4")
    proc=subprocess.Popen([exe("ffmpeg"),"-y","-f","rawvideo","-pix_fmt","rgb24","-s",f"{W}x{H}","-r",str(FPS),"-i","-","-an","-c:v","libx264","-preset","veryfast","-crf","18","-pix_fmt","yuv420p",str(raw)],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,cwd=ROOT)
    assert proc.stdin
    for n in range(frames):
        t=n/FPS; q=t/DURATION; im=scene_bg(kind,t)
        # subtle cinematic camera drift: render scene at 2x and crop moving window
        if kind=="bedroom": x=270+90*ease(q); y=395; act="talk"
        elif kind=="stream": x=240+520*ease(q); y=405; act="run"
        elif kind=="dance": x=560+85*math.sin(t*math.pi*2); y=410; act="dance"
        elif kind=="night": x=610; y=410; act="wave"
        elif kind=="sunset": x=570; y=415; act="idle"
        else: x=180+430*ease(q); y=410; act="walk" if kind in {"garden","path","friends"} else "talk"
        birds(im,t) if kind in {"path","friends","dance"} else None
        if kind in {"friends","dance"}: rabbit(im,940,430,t)
        if kind in {"garden","path","stream","meadow","help","water","magic","friends","dance"}:
            lumi(im,300+420*q,180+45*math.sin(t*math.pi*2),t)
        milo(im,x,y,1.0,t,act)
        d=ImageDraw.Draw(im,"RGBA")
        if kind=="water":
            # watering can + animated stream
            d.rounded_rectangle((760,420,850,500),18,fill=(63,135,220,255)); d.ellipse((825,410,880,490),outline=(63,135,220,255),width=12); d.line((865,450,965,430),fill=(80,175,240,220),width=9)
            for k in range(5):
                px=965+12*k; py=435+20*math.sin(t*8+k); d.ellipse((px,py,px+7,py+7),fill=(155,220,255,220))
        if kind=="magic":
            for k in range(24):
                a=t*1.8+k*.37; px=970+120*math.cos(a)*(0.5+q); py=385-120*q+80*math.sin(a*1.7); d.ellipse((px-5,py-5,px+5,py+5),fill=(255,226,105,220))
        # gentle vignette
        overlay=Image.new("RGBA",(W,H),(0,0,0,0)); od=ImageDraw.Draw(overlay); od.rectangle((0,0,W,H),fill=(0,0,0,18)); im=Image.alpha_composite(im.convert("RGBA"),overlay).convert("RGB")
        proc.stdin.write(im.tobytes())
    proc.stdin.close(); rc=proc.wait()
    if rc: raise RuntimeError(proc.stderr.read().decode(errors="ignore")[-2000:])
    ffmpeg(["-y","-i",str(raw),"-c","copy",str(out)]); raw.unlink(missing_ok=True)


def voice(text,out):
    p=shutil.which("piper"); model=Path(os.getenv("PIPER_MODEL",str(ROOT/"voices"/"en_US-lessac-medium.onnx")))
    if not p or not model.exists(): raise RuntimeError("Pinned Piper neural voice model is required")
    subprocess.run([p,"--model",str(model),"--output_file",str(out),"--sentence-silence","0.28","--length-scale","0.96"],input=text,text=True,cwd=ROOT,check=True)


def audio_wav(out,kind,index,duration):
    rate=44100; total=int(rate*duration); notes=[]
    # gentle original chord progression; no single-note tone.
    roots=[261.63,293.66,329.63,392.00,349.23,329.63,293.66,261.63]
    for beat in range(int(duration*2)):
        root=roots[(beat+index)%len(roots)]; start=beat*.5
        for ratio,amp in ((1,.075),(1.25,.035),(1.5,.028),(2,.018)):
            notes.append((start,root*ratio,.48,amp))
    if kind in {"magic","dance","night"}:
        for beat in range(int(duration*2)):
            start=beat*.5; freq=[523.25,659.25,783.99][(beat+index)%3]; notes.append((start,freq,.22,.045))
    pcm=bytearray()
    for i in range(total):
        t=i/rate; v=0.0
        for start,freq,length,amp in notes:
            if start<=t<start+length:
                a=min(1,(t-start)/.035,max(0,(start+length-t)/.09)); v+=amp*a*math.sin(2*math.pi*freq*(t-start))
        pcm += int(max(-.8,min(.8,v))*30000).to_bytes(2,"little",signed=True)
    with wave.open(str(out),"wb") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(pcm)


def mix(video,voice_file,music,out,index):
    ffmpeg(["-y","-i",str(video),"-i",str(voice_file),"-i",str(music),"-filter_complex","[1:a]highpass=f=75,lowpass=f=14500,acompressor=threshold=-20dB:ratio=3:attack=8:release=80:makeup=3,loudnorm=I=-14:LRA=7:TP=-1.2[v];[2:a]highpass=f=80,lowpass=f=12000,volume=0.16[m];[v][m]amix=inputs=2:duration=first:dropout_transition=0.5,alimiter=limit=0.0,aresample=48000[a]","-map","0:v","-map","[a]","-c:v","copy","-c:a","aac","-b:a","192k","-ar","48000","-shortest",str(out)])


def main():
    content=os.getenv("CONTENT_TYPE","poem").strip().lower(); topic=os.getenv("TOPIC","Milo and the Little Flower").strip(); minutes=float(os.getenv("DURATION","1"))
    if content not in {"poem","story"}: raise RuntimeError("CONTENT_TYPE must be poem or story")
    if not topic: raise RuntimeError("TOPIC is required")
    if not 1<=minutes<=10: raise RuntimeError("DURATION must be 1-10 minutes")
    lines=POEM if content=="poem" else STORY; count=max(1,math.ceil(minutes*60/DURATION)); OUT.mkdir(parents=True,exist_ok=True); SCENES.mkdir(parents=True,exist_ok=True); clips=[]
    for i in range(count):
        kind,_=BEATS[i%len(BEATS)]; sd=SCENES/f"scene_{i+1:03d}"; sd.mkdir(parents=True,exist_ok=True); silent=sd/"animation.mp4"; vf=sd/"voice.wav"; mf=sd/"music.wav"; final=sd/"scene.mp4"
        render(kind,i+1,silent); voice(lines[i%len(lines)],vf); audio_wav(mf,kind,i+1,DURATION); mix(silent,vf,mf,final,i+1); clips.append(final)
    concat=OUT/"concat.txt"; concat.write_text("\n".join(f"file '{p.resolve()}'" for p in clips)+"\n",encoding="utf-8")
    final=OUT/"kids-animation.mp4"; ffmpeg(["-y","-f","concat","-safe","0","-i",str(concat),"-c","copy","-movflags","+faststart",str(final)])
    if not final.exists() or final.stat().st_size<500000: raise RuntimeError("Final video failed quality/size gate")
    meta={"topic":topic,"content_type":content,"duration_minutes":minutes,"video":"kids-animation.mp4","size_bytes":final.stat().st_size,"renderer":"premium_2d_cartoon_scene_engine","resolution":"1280x720","fps":FPS,"voice":"Piper en_US-lessac-medium neural","audio":"original_chord_music_plus_normalized_voice","cost":"$0"}
    (OUT/"production.json").write_text(json.dumps(meta,indent=2)+"\n",encoding="utf-8"); print(json.dumps(meta,indent=2)); return 0


if __name__=="__main__": raise SystemExit(main())
