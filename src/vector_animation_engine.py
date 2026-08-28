from __future__ import annotations

import math, os, shutil, subprocess, wave
from pathlib import Path
from PIL import Image
import cairosvg

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'output'/'kids_animation'
FPS=24; W=1280; H=720; SCENE_SECONDS=6
SCENES=[('bedroom','Milo wakes'),('garden','Milo meets Lumi'),('path','Milo follows Lumi'),('stream','Milo crosses the stream'),('meadow','Milo discovers the flower'),('help','Milo helps the flower'),('water','Milo waters the flower'),('magic','Lumi and Milo see flower magic'),('friends','Milo meets new friends'),('dance','Milo and friends dance'),('sunset','Milo rests at sunset'),('night','Milo goes home under the sun and stars')]
POEM=["Wake up, Milo, morning is bright! Stretch your paws in golden light!","Skip through the garden, green and wide. Little Lumi dances by your side!","Follow the path and sing hello. Watch the happy leaves all blow!","Hop on the stones, splash in the stream. Every little adventure is a dream!","In the meadow, what do we see? A sleepy flower waiting patiently.","Kind little Milo kneels down low. A gentle helping hand can make things grow.","Tip the can and water slow. Tiny drops help flowers grow!","Open, open, petals bright. Golden sparkles fill the light!","Friends come hopping, friends come flying. Happy little hearts, no one is hiding!","Clap your paws and dance around. Kindness makes a happy sound!","When the sun sinks soft and low, Milo sees how kindness grows.","Goodnight, friends, the stars shine through. Tomorrow brings adventures new!"]
STORY=["Milo woke with a sleepy yawn. A tiny glow twinkled outside his window.","He opened the door and met Lumi, a friendly little firefly with a warm golden light.","Lumi flew down the garden path, and Milo followed with three cheerful birds.","At the stream Milo crossed the stones. Splash! He nearly slipped, then laughed.","Across the stream he heard a tiny cry. A little flower was thirsty and its petals were closed.","Milo knelt beside the flower and promised to help. He hurried for his watering can.","Drop by drop, Milo watered the flower. Slowly its leaves lifted toward the sun.","The flower opened with a sparkle. Lumi danced around it like a tiny star.","A rabbit and the birds arrived. Everyone gathered to see the beautiful flower.","They danced together because kindness had brought them all to the same place.","At sunset Milo rested beside the flower and smiled at his new friends.","Milo waved goodnight. Lumi lit the path home, and tomorrow another adventure would begin."]

def esc(s): return s.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
def svg_scene(kind,action,t):
    p=t/SCENE_SECONDS; night=kind=='night'; sunset=kind=='sunset'
    sky='#17234d' if night else '#f3a56f' if sunset else '#8ed6f2'
    ground='#3d7250' if night else '#74b866'; sun='#ffd96b'
    if kind=='bedroom': bg=f'''<rect width="1280" height="720" fill="#f4dfbf"/><rect y="510" width="1280" height="210" fill="#b98d67"/><rect x="820" y="110" width="300" height="250" rx="18" fill="#9ed6ee" stroke="#654f4a" stroke-width="10"/><circle cx="970" cy="205" r="62" fill="#ffe18a"/><rect x="110" y="350" width="430" height="170" rx="35" fill="#5b86b8"/><text x="640" y="80" font-family="sans-serif" font-size="42" font-weight="700" fill="#684f45">GOOD MORNING, MILO!</text>'''
    else:
        bg=f'''<rect width="1280" height="720" fill="{sky}"/><circle cx="1050" cy="130" r="82" fill="{sun}"/><path d="M0 440 Q180 300 350 440 T700 420 T1280 430 V720 H0Z" fill="#689d65"/><path d="M0 535 Q300 470 600 535 T1280 520 V720 H0Z" fill="{ground}"/>'''
        if kind=='path': bg+='''<path d="M470 720 Q600 500 640 400 Q690 500 850 720Z" fill="#c7a36e"/>'''
        if kind=='stream': bg+='''<path d="M300 720 Q500 530 570 390 Q700 500 980 720Z" fill="#48b9e6" opacity=".9"/><ellipse cx="520" cy="525" rx="75" ry="28" fill="#b9b5a8"/><ellipse cx="680" cy="585" rx="75" ry="28" fill="#b9b5a8"/>'''
        for x in (100,1120): bg+=f'''<rect x="{x-12}" y="330" width="24" height="150" rx="10" fill="#765036"/><circle cx="{x}" cy="310" r="95" fill="#4f9857"/><circle cx="{x-55}" cy="350" r="65" fill="#5ca35e"/>'''
        if kind in {'meadow','help','water','magic','friends','dance','sunset'}:
            bg+='''<path d="M1010 490 Q1010 390 1010 330" stroke="#39814d" stroke-width="14"/><g fill="#f28fb5"><ellipse cx="1010" cy="315" rx="28" ry="48"/><ellipse cx="1010" cy="315" rx="28" ry="48" transform="rotate(72 1010 315)"/><ellipse cx="1010" cy="315" rx="28" ry="48" transform="rotate(144 1010 315)"/><ellipse cx="1010" cy="315" rx="28" ry="48" transform="rotate(216 1010 315)"/><ellipse cx="1010" cy="315" rx="28" ry="48" transform="rotate(288 1010 315)"/></g><circle cx="1010" cy="315" r="24" fill="#ffd45d"/>'''
        if night:
            for x,y in [(110,90),(220,160),(390,80),(560,130),(760,75),(930,180),(1150,100)]: bg+=f'<circle cx="{x}" cy="{y}" r="5" fill="#fff4b0"/>'
    mx=250+520*(3*p*p-2*p*p*p) if kind not in {'bedroom','meadow','help','water','sunset','night'} else 520
    bounce=8*math.sin(t*math.pi*2) if action in {'walk','dance','run'} else 0
    arm=30*math.sin(t*math.pi*2) if action in {'dance','wave','walk'} else 0
    blink='ry="3"' if (t%4.0)>3.82 else 'ry="12"'
    mouth=10+7*abs(math.sin(t*math.pi*4))
    milo=f'''<g transform="translate({mx} {390+bounce}) scale(.92)"><ellipse cx="0" cy="205" rx="72" ry="18" fill="#234" opacity=".18"/><path d="M-58 100 L-45 190 L-10 190 L0 105Z" fill="#356fc0"/><path d="M10 105 L15 190 L50 190 L58 100Z" fill="#285ba7"/><ellipse cx="0" cy="45" rx="82" ry="95" fill="#c98d55" stroke="#6d482f" stroke-width="6"/><path d="M-68 45 Q0 110 68 45 L62 110 Q0 145 -62 110Z" fill="#3c8bd4"/><ellipse cx="-68" cy="-50" rx="30" ry="55" fill="#a96e42"/><ellipse cx="68" cy="-50" rx="30" ry="55" fill="#a96e42"/><circle cx="0" cy="-35" r="82" fill="#d49a60" stroke="#6d482f" stroke-width="6"/><ellipse cx="-30" cy="-42" rx="13" {blink} fill="#2b2420"/><ellipse cx="30" cy="-42" rx="13" {blink} fill="#2b2420"/><ellipse cx="0" cy="-8" rx="13" ry="9" fill="#51352f"/><ellipse cx="0" cy="18" rx="{mouth}" ry="7" fill="#7d3e4c"/><path d="M-60 80 Q-105 125 -100 {135-arm}" stroke="#c98d55" stroke-width="20" stroke-linecap="round"/><path d="M60 80 Q105 125 100 {135+arm}" stroke="#c98d55" stroke-width="20" stroke-linecap="round"/><circle cx="-102" cy="{135-arm}" r="13" fill="#c98d55"/><circle cx="102" cy="{135+arm}" r="13" fill="#c98d55"/></g>'''
    lumi_x=360+480*p; lumi_y=180+45*math.sin(t*math.pi*2); lumi=f'''<g><circle cx="{lumi_x}" cy="{lumi_y}" r="42" fill="#ffe66d" opacity=".12"/><circle cx="{lumi_x}" cy="{lumi_y}" r="24" fill="#ffe66d" opacity=".25"/><circle cx="{lumi_x}" cy="{lumi_y}" r="9" fill="#fff4a8"/></g>'''
    magic=''
    if kind=='magic':
        for i in range(18):
            a=t*2+i*.9; x=1010+70*math.cos(a); y=315-110*p+50*math.sin(a*1.7); magic+=f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{3+i%3}" fill="#ffe66d" opacity=".85"/>'
    rabbit='''<g transform="translate(850 500)"><ellipse cx="0" cy="0" rx="48" ry="58" fill="#eeeae0" stroke="#aaa59c" stroke-width="5"/><ellipse cx="-25" cy="-75" rx="18" ry="50" fill="#eeeae0"/><ellipse cx="25" cy="-75" rx="18" ry="50" fill="#eeeae0"/><circle cx="-14" cy="-8" r="5"/><circle cx="14" cy="-8" r="5"/></g>''' if kind in {'friends','dance'} else ''
    birds=''.join(f'<path d="M{x} {y} q20 {-12+10*math.sin(t*8+i)} 40 0 q-20 12 -40 0" fill="none" stroke="#435c7a" stroke-width="6"/>' for i,(x,y) in enumerate([(150,180),(250,135),(340,200)])) if kind in {'path','friends','dance'} else ''
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">{bg}{birds}{milo}{lumi}{rabbit}{magic}<text x="64" y="660" font-family="sans-serif" font-size="30" font-weight="700" fill="white" stroke="#203" stroke-width="6" paint-order="stroke">{esc(kind.title())}</text></svg>'''

def render_scene(kind,action,out):
    frames=int(SCENE_SECONDS*FPS); raw=out.with_suffix('.mp4'); proc=subprocess.Popen(['ffmpeg','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-an','-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p',str(raw)],stdin=subprocess.PIPE)
    for n in range(frames):
        t=n/FPS; png=Path('/tmp/frame.svg'); png.write_text(svg_scene(kind,action,t),encoding='utf-8'); data=cairosvg.svg2png(bytestring=png.read_bytes(),output_width=W,output_height=H); proc.stdin.write(data)
    proc.stdin.close(); rc=proc.wait()
    if rc: raise RuntimeError('vector render failed')
    shutil.move(raw,out)

def voice(text,out):
    piper=shutil.which('piper'); model=Path(os.environ.get('PIPER_MODEL','voices/en_US-lessac-medium.onnx'))
    if not piper or not model.exists(): raise RuntimeError('Pinned Piper neural voice is required')
    subprocess.run([piper,'--model',str(model),'--output_file',str(out),'--sentence-silence','0.25'],input=text,text=True,check=True,cwd=ROOT)

def main():
    content=os.getenv('CONTENT_TYPE','poem'); duration=float(os.getenv('DURATION','1'))
    if content not in {'poem','story'}: raise RuntimeError('CONTENT_TYPE must be poem or story')
    if not 1 <= duration <= 10: raise RuntimeError('DURATION must be between 1 and 10 minutes')
    lines=POEM if content=='poem' else STORY
    OUT.mkdir(parents=True,exist_ok=True); scenes=[]
    for i,(kind,action) in enumerate(SCENES):
        sd=OUT/'scenes'/f'{i+1:03d}'; sd.mkdir(parents=True,exist_ok=True); v=sd/'video.mp4'; a=sd/'voice.wav'; render_scene(kind,action,v); voice(lines[i%len(lines)],a); final=sd/'scene.mp4'
        subprocess.run(['ffmpeg','-y','-i',str(v),'-i',str(a),'-filter_complex','[1:a]highpass=f=80,lowpass=f=12000,acompressor=threshold=-18dB:ratio=3:attack=5:release=80,volume=1.8,aresample=48000[a]','-map','0:v','-map','[a]','-c:v','copy','-c:a','aac','-b:a','192k','-ar','48000','-shortest',str(final)],check=True,cwd=ROOT)
        scenes.append(final)
    concat=OUT/'concat.txt'; concat.write_text('\n'.join(f"file '{p.resolve()}'" for p in scenes)+'\n'); final=OUT/'kids-animation.mp4'
    subprocess.run(['ffmpeg','-y','-f','concat','-safe','0','-i',str(concat),'-c','copy','-movflags','+faststart',str(final)],check=True,cwd=ROOT)
    if final.stat().st_size<500000: raise RuntimeError('rendered video failed quality gate')
    print(f'RENDERED {final} {final.stat().st_size} bytes')

if __name__=='__main__': main()
