from __future__ import annotations

import math
import os
import shutil
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output" / "kids_animation"
FPS, W, H = 24, 960, 540
SCENES = [
    ("bedroom", 12, "Milo: What's that little light?"),
    ("garden", 12, "Milo: Hello, little friend!"),
    ("path", 12, "Milo: Don't worry. We'll help you."),
    ("stream", 12, "Milo: One step... two steps... we can do it!"),
    ("meadow", 12, "Milo: We found it!"),
    ("home", 12, "Narrator: Kindness can light even the darkest path."),
    ("celebration", 12, "Milo: A little kindness makes a big light!"),
    ("night", 6, "Narrator: And tomorrow, another adventure will begin."),
]


def run(cmd: list[str]) -> None:
    if shutil.which(cmd[0]) is None:
        raise RuntimeError(f"Missing executable: {cmd[0]}")
    subprocess.run(cmd, cwd=ROOT, check=True)


def bg(scene: str, t: float) -> Image.Image:
    im = Image.new("RGB", (W, H), (125, 195, 245)); d = ImageDraw.Draw(im)
    if scene == "bedroom":
        d.rectangle((0, 0, W, H), fill=(245, 222, 188)); d.rectangle((0, 390, W, H), fill=(198, 158, 118))
        d.rectangle((70, 220, 360, 390), fill=(91, 137, 194), outline=(65, 85, 120), width=6)
        d.rectangle((600, 90, 820, 285), fill=(164, 211, 245), outline=(100, 140, 170), width=5)
        d.ellipse((680, 120, 770, 210), fill=(255, 218, 91))
        return im
    sky = (248, 170, 120) if scene in {"home"} else (125, 195, 245)
    if scene == "night": sky = (31, 43, 93)
    d.rectangle((0, 0, W, 360), fill=sky); d.rectangle((0, 350, W, H), fill=(102, 178, 93))
    if scene == "home": d.ellipse((760, 235, 880, 355), fill=(255, 205, 104))
    if scene == "night":
        for x, y in [(90,70),(180,145),(320,55),(480,105),(640,65),(830,135)]: d.ellipse((x,y,x+6,y+6), fill=(255,244,180))
    # hills and trees
    d.polygon([(0,360),(170,255),(330,360),(520,235),(740,360),(960,250),(960,540),(0,540)], fill=(118,176,92))
    for x in (75, 860):
        d.rectangle((x-10, 270, x+10, 410), fill=(105,72,43)); d.ellipse((x-65,205,x+65,315), fill=(63,139,74))
    if scene in {"garden","meadow","celebration"}:
        for x in range(30, 950, 70):
            y = 405 + int(18*math.sin(x))
            d.line((x,y,x,y+28), fill=(45,120,55), width=3); d.ellipse((x-8,y-8,x+8,y+8), fill=(242,112,170))
    if scene == "path": d.polygon([(420,540),(455,355),(505,355),(650,540)], fill=(204,167,116))
    if scene == "stream":
        d.polygon([(350,540),(425,330),(535,330),(680,540)], fill=(70,165,220))
        for x in (390,455,520,585): d.ellipse((x,425,x+55,455), fill=(174,168,160))
    return im


def milo(draw: ImageDraw.ImageDraw, x: float, y: float, scale: float, phase: float, mood: str = "happy") -> None:
    s=scale; bob=5*math.sin(phase*2); yy=y+bob
    # legs with walking cycle
    step=18*math.sin(phase*5)
    draw.line((x-38*s,yy+120*s,x-45*s+step,yy+175*s),fill=(70,72,100),width=max(3,int(12*s)))
    draw.line((x+38*s,yy+120*s,x+45*s-step,yy+175*s),fill=(70,72,100),width=max(3,int(12*s)))
    # body
    draw.ellipse((x-75*s,yy+45*s,x+75*s,yy+155*s),fill=(62,125,215),outline=(39,75,140),width=max(2,int(4*s)))
    # arms swing
    arm=25*math.sin(phase*5)
    draw.line((x-55*s,yy+70*s,x-105*s,yy+105*s+arm),fill=(195,130,72),width=max(3,int(13*s)))
    draw.line((x+55*s,yy+70*s,x+105*s,yy+105*s-arm),fill=(195,130,72),width=max(3,int(13*s)))
    # ears/head
    draw.ellipse((x-72*s,yy-90*s,x-5*s,yy-10*s),fill=(143,88,48),outline=(95,58,35),width=max(2,int(4*s)))
    draw.ellipse((x+5*s,yy-90*s,x+72*s,yy-10*s),fill=(143,88,48),outline=(95,58,35),width=max(2,int(4*s)))
    draw.ellipse((x-85*s,yy-105*s,x+85*s,yy+65*s),fill=(203,142,76),outline=(105,70,40),width=max(2,int(4*s)))
    # eyes and brows
    eye_y=yy-30*s; blink=(int(phase*3)%7)==0
    if blink:
        draw.line((x-48*s,eye_y,x-20*s,eye_y),fill=(55,40,30),width=max(2,int(4*s))); draw.line((x+20*s,eye_y,x+48*s,eye_y),fill=(55,40,30),width=max(2,int(4*s)))
    else:
        draw.ellipse((x-49*s,eye_y-15*s,x-20*s,eye_y+15*s),fill=(48,35,30)); draw.ellipse((x+20*s,eye_y-15*s,x+49*s,eye_y+15*s),fill=(48,35,30))
        draw.ellipse((x-40*s,eye_y-10*s,x-32*s,eye_y-2*s),fill="white"); draw.ellipse((x+29*s,eye_y-10*s,x+37*s,eye_y-2*s),fill="white")
    # muzzle + animated mouth
    draw.ellipse((x-38*s,yy+5*s,x+38*s,yy+45*s),fill=(239,191,125)); draw.ellipse((x-7*s,yy+8*s,x+7*s,yy+20*s),fill=(48,35,30))
    mouth=10+9*abs(math.sin(phase*7))
    draw.ellipse((x-18*s,yy+24*s,x+18*s,yy+24*s+mouth*s),fill=(85,35,45))
    if mood == "surprised": draw.ellipse((x-14*s,yy+20*s,x+14*s,yy+48*s),fill=(85,35,45))


def lumi(draw: ImageDraw.ImageDraw, x: float, y: float, phase: float) -> None:
    r=10+3*math.sin(phase*6); draw.ellipse((x-r,y-r,x+r,y+r),fill=(255,240,120),outline=(255,210,70),width=3)
    for a in (0,math.pi/2,math.pi,3*math.pi/2):
        xx=x+math.cos(a)*20; yy=y+math.sin(a)*20; draw.ellipse((xx-3,yy-3,xx+3,yy+3),fill=(255,250,185))


def sfx(scene: str, seconds: float, out: Path) -> None:
    # Small, pleasant synthetic cues; no loud constant tone bed.
    freq={"bedroom":440,"garden":660,"path":523,"stream":392,"meadow":494,"home":349,"celebration":784,"night":330}[scene]
    run(["ffmpeg","-y","-f","lavfi","-i",f"sine=frequency={freq}:sample_rate=48000:duration={seconds}","-af","afade=t=in:st=0:d=0.08,afade=t=out:st=0.6:d=0.4,volume=0.045","-c:a","pcm_s16le",str(out)])


def main() -> int:
    OUT.mkdir(parents=True,exist_ok=True); frames=OUT/"golden_frames"; frames.mkdir(exist_ok=True)
    frame_no=0
    for si,(scene,duration,_dialogue) in enumerate(SCENES):
        n=int(duration*FPS)
        for j in range(n):
            t=j/FPS; p=t/max(duration,1); im=bg(scene,t); d=ImageDraw.Draw(im)
            # Story-specific blocking: Milo changes position/action instead of sliding constantly.
            if scene=="bedroom": x=220+18*math.sin(t*2); y=300
            elif scene in {"garden","path"}: x=170+500*p; y=300
            elif scene=="stream": x=330+170*p; y=285+18*math.sin(t*4)
            elif scene=="meadow": x=350+40*math.sin(t*2); y=300
            elif scene=="home": x=430+170*p; y=300
            elif scene=="celebration": x=480+45*math.sin(t*3); y=300
            else: x=430; y=300
            mood="surprised" if scene=="meadow" and p<.35 else "happy"
            milo(d,x,y,1.0,t,mood)
            if scene in {"garden","path","meadow","stream","home","celebration"}:
                lx=360+170*math.sin(t*1.7); ly=190+55*math.sin(t*2.1); lumi(d,lx,ly,t)
            if scene=="meadow":
                # animated flower with opening petals
                openness=min(1,p*1.8); cx,cy=700,365; r=35+18*openness
                for a in range(0,360,72):
                    rr=math.radians(a); px=cx+int(math.cos(rr)*r); py=cy+int(math.sin(rr)*r); d.ellipse((px-20,py-20,px+20,py+20),fill=(246,120,180))
                d.ellipse((cx-18,cy-18,cx+18,cy+18),fill=(255,205,70))
            if scene=="celebration":
                for k in range(8):
                    xx=180+k*95; yy=130+45*math.sin(t*4+k); d.ellipse((xx,yy,xx+7,yy+7),fill=(255,230,110))
            # cinematic letterbox is intentionally avoided; keep child-friendly full frame.
            im.save(frames/f"f_{frame_no:05d}.png"); frame_no+=1
    silent=OUT/"golden_silent.mp4"
    run(["ffmpeg","-y","-framerate",str(FPS),"-i",str(frames/"f_%05d.png"),"-c:v","libx264","-preset","veryfast","-pix_fmt","yuv420p","-r",str(FPS),str(silent)])
    # Natural-ish local narration is kept, but music is no longer a constant sine tone.
    narration=OUT/"golden_voice.wav"
    text=" ".join(s[2] for s in SCENES)
    run(["espeak-ng","-v","en-us+f3","-s","142","-p","58","-a","165","-w",str(narration),text])
    final=OUT/"kids-animation.mp4"
    run(["ffmpeg","-y","-i",str(silent),"-i",str(narration),"-filter_complex","[1:a]apad,volume=1[a]","-map","0:v","-map","[a]","-c:v","copy","-c:a","aac","-b:a","128k","-shortest","-movflags","+faststart",str(final)])
    if not final.exists() or final.stat().st_size < 100000: raise RuntimeError("golden episode was not rendered")
    print(f"Golden episode created: {final} ({final.stat().st_size} bytes)")
    return 0

if __name__ == "__main__": raise SystemExit(main())
