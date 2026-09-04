"""Richer CPU-safe Blender animation backend for the normal video pipeline.

This intentionally lives beside the existing kids engines. It creates an
original stylized fox-like hero, per-scene 3D environments, facial acting,
body gestures, camera choreography and lighting using Blender/EEVEE only.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
PLAN = OUTPUT / "normal_production" / "director_plan.json"
WORK = OUTPUT / "normal_production" / "3d_animation_v2"
FINAL = OUTPUT / "normal_production" / "3d-animation.mp4"


def blender_binary() -> str:
    return os.getenv("BLENDER_BIN") or shutil.which("blender") or ""


def theme_for(scene: dict) -> str:
    text = " ".join(str(scene.get(k, "")) for k in ("narration", "subject", "location", "action", "visual_prompt")).lower()
    groups = {
        "ocean": ("ocean", "sea", "underwater", "fish", "whale", "coral"),
        "forest": ("forest", "jungle", "tree", "bird", "frog", "wood"),
        "desert": ("desert", "sand", "sahara", "dune", "canyon"),
        "snow": ("snow", "ice", "arctic", "glacier", "polar", "winter"),
        "volcano": ("volcano", "lava", "eruption", "magma"),
        "space": ("space", "planet", "star", "galaxy", "moon", "cosmic"),
        "city": ("city", "street", "building", "traffic", "tokyo"),
    }
    for name, words in groups.items():
        if any(w in text for w in words):
            return name
    return "meadow"


def clean(value: object) -> str:
    return " ".join(str(value or "").split())


def make_script(scenes: list[dict], fps: int, width: int, height: int, out_pattern: str) -> str:
    # Keep the first 12 beats: 12 x 2.5s = 30s, safely inside the Shorts gate.
    beats = scenes[:12]
    payload = json.dumps([
        {
            "n": i + 1,
            "text": clean(s.get("narration") or s.get("action") or s.get("visual_prompt")),
            "action": clean(s.get("action")),
            "emotion": clean(s.get("emotion")),
            "shot": clean(s.get("shot")),
            "camera": clean(s.get("camera_motion")),
            "theme": theme_for(s),
        }
        for i, s in enumerate(beats)
    ])
    return f'''import bpy, math, json
from mathutils import Vector

SCENES = json.loads({payload!r})
FPS = {fps}
W, H = {width}, {height}
OUT = {out_pattern!r}
DUR = 2.5

# ---------- materials ----------
def mat(name, color, rough=.45, metallic=0.0, emission=None):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1.0)
    m.use_nodes = True
    bs = m.node_tree.nodes.get('Principled BSDF')
    if bs:
        bs.inputs['Base Color'].default_value = (*color, 1.0)
        bs.inputs['Roughness'].default_value = rough
        bs.inputs['Metallic'].default_value = metallic
        if emission:
            bs.inputs['Emission Color'].default_value = (*emission, 1.0)
            bs.inputs['Emission Strength'].default_value = 2.5
    return m

ORANGE=mat('Hero Orange',(0.92,0.28,0.055),.34)
CREAM=mat('Hero Cream',(1.0,0.78,0.46),.42)
WHITE=mat('Eye White',(0.98,0.99,1.0),.18)
DARK=mat('Pupil',(0.008,0.012,0.02),.18)
MOUTH=mat('Mouth',(0.18,0.008,0.018),.3)
GROUND=mat('Meadow',(0.12,0.34,0.13),.85)
TREE=mat('Leaf',(0.07,0.42,0.13),.72)
TRUNK=mat('Bark',(0.30,0.12,0.045),.85)
WATER=mat('Water',(0.025,0.28,0.58),.2)
SAND=mat('Sand',(0.72,0.42,0.16),.9)
SNOW=mat('Snow',(0.86,0.93,1.0),.65)
ROCK=mat('Rock',(0.18,0.19,0.23),.9)
LAVA=mat('Lava',(0.95,0.09,0.01),.3,emission=(1.0,.04,.005))
SPACE=mat('Space',(0.004,0.007,0.025),.95)
STAR=mat('Star',(0.5,0.8,1.0),.18,emission=(0.2,0.65,1.0))
CITY=mat('City',(0.08,0.13,0.25),.65)
GOLD=mat('City Glow',(1.0,0.48,0.08),.25,emission=(1.0,.25,.02))


def link_obj(obj, collection):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    collection.objects.link(obj)


def uv(name, loc, scale, material, collection, seg=24, rings=12):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=rings, location=loc)
    o=bpy.context.object; o.name=name; o.scale=scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.data.materials.append(material); bpy.ops.object.shade_smooth(); link_obj(o,collection); return o


def cube(name, loc, scale, material, collection, bevel=.12):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o=bpy.context.object; o.name=name; o.scale=scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.data.materials.append(material)
    if bevel:
        mod=o.modifiers.new('Soft Edges','BEVEL'); mod.width=bevel; mod.segments=3
    link_obj(o,collection); return o


def cyl(name, loc, radius, depth, material, collection, rot=(0,0,0)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=radius, depth=depth, location=loc, rotation=rot)
    o=bpy.context.object; o.name=name; o.data.materials.append(material); bpy.ops.object.shade_smooth(); link_obj(o,collection); return o


def cone(name, loc, r1, r2, depth, material, collection):
    bpy.ops.mesh.primitive_cone_add(vertices=20, radius1=r1, radius2=r2, depth=depth, location=loc)
    o=bpy.context.object; o.name=name; o.data.materials.append(material); bpy.ops.object.shade_smooth(); link_obj(o,collection); return o


def new_collection(name):
    c=bpy.data.collections.new(name); bpy.context.scene.collection.children.link(c); return c


def tree(c,x,y,s=1.0):
    cyl('Trunk',(x,y,1.2*s),.24*s,2.4*s,TRUNK,c)
    uv('Canopy',(x,y,2.7*s),(1.0*s,.9*s,1.0*s),TREE,c)
    uv('Canopy',(x+.45*s,y,3.25*s),(.65*s,.6*s,.65*s),TREE,c)


def environment(theme, idx):
    c=new_collection(f'ENV_{idx:02d}_{theme}')
    if theme=='ocean':
        cube('SeaFloor',(0,2,-.25),(9,9,.2),WATER,c,.05)
        for x,y,h in [(-4,3,1.5),(-2,6,2.0),(2,5,1.4),(4,2,1.8)]:
            cone('Coral',(x,y,h/2),.35,.05,h,ORANGE,c)
    elif theme=='forest':
        cube('ForestFloor',(0,2,-.15),(10,10,.15),GROUND,c,.02)
        for x,y,s in [(-5,4,1.0),(-3,7,.8),(3,6,1.1),(5,2,.85),(-5,0,.9)]: tree(c,x,y,s)
    elif theme=='desert':
        cube('SandFloor',(0,2,-.15),(10,10,.15),SAND,c,.02)
        for x,y,s in [(-4,5,1.2),(3,6,.9),(4,1,1.4)]: uv('DuneRock',(x,y,.6),(s, s*.75, s*.65),ROCK,c)
    elif theme=='snow':
        cube('SnowFloor',(0,2,-.15),(10,10,.15),SNOW,c,.02)
        for x,y,s in [(-4,5,1.4),(3,6,1.0),(4,1,1.3)]: cone('SnowPeak',(x,y,s),s,0,2*s,SNOW,c)
    elif theme=='volcano':
        cube('VolcanicFloor',(0,2,-.15),(10,10,.15),ROCK,c,.02)
        cone('Volcano',(3,5,1.8),2.8,.6,3.6,ROCK,c)
        uv('LavaGlow',(3,4.8,3.7),(.75,.75,.15),LAVA,c)
    elif theme=='space':
        cube('SpaceFloor',(0,2,-.15),(10,10,.15),SPACE,c,.02)
        for x,y,z in [(-5,4,5),(4,6,4),(3,2,6),(-3,0,5),(-1,8,7),(5,0,7)]: uv('Star',(x,y,z),(.09,.09,.09),STAR,c,12,8)
        uv('Planet',(4,7,2.5),(1.7,1.7,1.7),STAR,c)
    elif theme=='city':
        cube('Street',(0,2,-.15),(10,10,.15),ROCK,c,.02)
        for x in (-5,-3,2,4.5):
            cube('Building',(x,7,2.0),(1.0,1.2,2.0),CITY,c,.08)
            for z in (1.2,2.0,2.8): cube('Window',(x,-.22+7,z),(.18,.04,.12),GOLD,c,.02)
    else:
        cube('MeadowFloor',(0,2,-.15),(10,10,.15),GROUND,c,.02)
        for x,y,s in [(-5,5,.9),(4,6,.75),(5,1,.8)]: tree(c,x,y,s)
    return c


def character():
    c=new_collection('HERO')
    root=bpy.data.objects.new('HERO_ROOT',None); c.objects.link(root)
    body=uv('HeroBody',(0,0,1.55),(.72,.48,.9),ORANGE,c); body.parent=root
    belly=uv('HeroBelly',(0,-.46,1.42),(.42,.075,.5),CREAM,c); belly.parent=root
    head=uv('HeroHead',(0,-.02,2.55),(.78,.60,.66),ORANGE,c); head.parent=root
    muzzle=uv('HeroMuzzle',(0,-.60,2.38),(.30,.09,.22),CREAM,c); muzzle.parent=root
    parts={'root':root,'mouth':uv('HeroMouth',(0,-.685,2.38),(.15,.025,.055),MOUTH,c),
           'tail':uv('HeroTail',(.72,.18,1.62),(.55,.20,.30),ORANGE,c),
           'eyeL':None,'eyeR':None,'pupilL':None,'pupilR':None,'armL':None,'armR':None}
    parts['mouth'].parent=root; parts['tail'].parent=root
    for side,x in [('L',-.27),('R',.27)]:
        e=uv('HeroEye'+side,(x,-.56,2.66),(.19,.075,.22),WHITE,c); e.parent=root; parts['eye'+side]=e
        p=uv('HeroPupil'+side,(x,-.635,2.66),(.075,.035,.10),DARK,c); p.parent=root; parts['pupil'+side]=p
    for side,x in [('L',-.78),('R',.78)]:
        a=cyl('HeroArm'+side,(x,0,1.62),.15,.82,ORANGE,c,rot=(0,math.pi/2,0)); a.parent=root; parts['arm'+side]=a
    for side,x in [('L',-.30),('R',.30)]:
        leg=cyl('HeroLeg'+side,(x,0,.67),.18,.72,ORANGE,c); leg.parent=root
        foot=uv('HeroFoot'+side,(x,-.16,.28),(.25,.34,.15),CREAM,c); foot.parent=root
    for side,x in [('L',-.42),('R',.42)]:
        ear=cone('HeroEar'+side,(x,0,3.20),.24,0,.48,ORANGE,c); ear.parent=root
        inner=cone('HeroInnerEar'+side,(x,-.03,3.19),.11,0,.26,CREAM,c); inner.parent=root
    return parts


def look_at(obj, point):
    obj.rotation_euler=(Vector(point)-obj.location).to_track_quat('-Z','Y').to_euler()


def camera_setup():
    bpy.ops.object.camera_add(location=(0,-12,3.0)); cam=bpy.context.object; cam.name='CinematicCamera'; bpy.context.scene.camera=cam
    cam.data.lens=52; cam.data.sensor_width=36
    return cam


def lights():
    bpy.ops.object.light_add(type='AREA', location=(-4,-5,7)); key=bpy.context.object; key.data.energy=900; key.data.shape='DISK'; key.data.size=5; look_at(key,(0,0,1.8))
    bpy.ops.object.light_add(type='AREA', location=(4,-3,4)); fill=bpy.context.object; fill.data.energy=420; fill.data.size=4; look_at(fill,(0,0,2))
    bpy.ops.object.light_add(type='AREA', location=(0,4,6)); rim=bpy.context.object; rim.data.energy=700; rim.data.size=3; rim.data.color=(.35,.6,1.0); look_at(rim,(0,0,2))


def set_world(theme):
    w=bpy.context.scene.world or bpy.data.worlds.new('World'); bpy.context.scene.world=w; w.use_nodes=True
    bg=w.node_tree.nodes.get('Background');
    colors={'ocean':(.01,.06,.16,1),'forest':(.015,.06,.02,1),'desert':(.15,.07,.025,1),'snow':(.10,.15,.22,1),'volcano':(.08,.008,.003,1),'space':(.001,.002,.01,1),'city':(.015,.025,.07,1),'meadow':(.025,.07,.035,1)}
    bg.inputs['Color'].default_value=colors.get(theme,colors['meadow']); bg.inputs['Strength'].default_value=.28


def animate(parts, start, end, emotion, action):
    root=parts['root']; mouth=parts['mouth']; tail=parts['tail']; armL=parts['armL']; armR=parts['armR']
    text=(emotion+' '+action).lower()
    root.location=(0,0,0); root.rotation_euler=(0,0,0); root.keyframe_insert('location',frame=start); root.keyframe_insert('rotation_euler',frame=start)
    root.location=(0,0,.08); root.keyframe_insert('location',frame=start+8)
    mid=(start+end)//2
    if any(k in text for k in ('walk','run','move','travel','approach')):
        root.location.x=-1.25; root.rotation_euler.y=-.10; root.keyframe_insert('location',frame=start); root.keyframe_insert('rotation_euler',frame=start)
        root.location.x=1.15; root.rotation_euler.y=.10; root.keyframe_insert('location',frame=mid); root.keyframe_insert('rotation_euler',frame=mid)
        root.location.x=.25; root.rotation_euler.y=0; root.keyframe_insert('location',frame=end); root.keyframe_insert('rotation_euler',frame=end)
        armL.rotation_euler.z=-.55; armR.rotation_euler.z=.55; armL.keyframe_insert('rotation_euler',frame=start); armR.keyframe_insert('rotation_euler',frame=start)
        armL.rotation_euler.z=.55; armR.rotation_euler.z=-.55; armL.keyframe_insert('rotation_euler',frame=mid); armR.keyframe_insert('rotation_euler',frame=mid)
        armL.rotation_euler.z=0; armR.rotation_euler.z=0; armL.keyframe_insert('rotation_euler',frame=end); armR.keyframe_insert('rotation_euler',frame=end)
    elif any(k in text for k in ('jump','excited','celebrate')):
        root.location.z=.70; root.keyframe_insert('location',frame=mid-5); root.location.z=0; root.keyframe_insert('location',frame=mid+5)
        armL.rotation_euler.z=-1.0; armR.rotation_euler.z=1.0; armL.keyframe_insert('rotation_euler',frame=mid); armR.keyframe_insert('rotation_euler',frame=mid)
    elif any(k in text for k in ('surprise','shock','discover','amazed')):
        root.rotation_euler.y=.22; root.keyframe_insert('rotation_euler',frame=mid); root.rotation_euler.y=-.16; root.keyframe_insert('rotation_euler',frame=mid+10)
        mouth.scale=(1.0,1.0,2.0); mouth.keyframe_insert('scale',frame=mid); mouth.scale=(1,1,1); mouth.keyframe_insert('scale',frame=end)
    elif any(k in text for k in ('sad','afraid','scared','worried')):
        root.location.z=-.08; root.keyframe_insert('location',frame=mid); mouth.scale=(.8,1,0.55); mouth.keyframe_insert('scale',frame=mid)
    else:
        root.rotation_euler.z=.08; root.keyframe_insert('rotation_euler',frame=mid); root.rotation_euler.z=0; root.keyframe_insert('rotation_euler',frame=end)
    # expressive tail wag and blink
    tail.rotation_euler.y=.35; tail.keyframe_insert('rotation_euler',frame=start); tail.rotation_euler.y=-.35; tail.keyframe_insert('rotation_euler',frame=mid); tail.rotation_euler.y=.2; tail.keyframe_insert('rotation_euler',frame=end)
    for eye in (parts['eyeL'],parts['eyeR']):
        eye.scale.z=.18; eye.keyframe_insert('scale',frame=mid-2); eye.scale.z=1; eye.keyframe_insert('scale',frame=mid+2)
    for obj in (root,mouth,tail,armL,armR,parts['eyeL'],parts['eyeR']):
        if obj.animation_data and obj.animation_data.action:
            for fc in obj.animation_data.action.fcurves:
                for kp in fc.keyframe_points: kp.interpolation='BEZIER'


def visibility(collections, active, start, end):
    for c in collections:
        for o in c.objects:
            o.hide_render=True; o.keyframe_insert('hide_render',frame=start)
            o.keyframe_insert('hide_render',frame=end)
    for o in active.objects:
        o.hide_render=False; o.keyframe_insert('hide_render',frame=start); o.keyframe_insert('hide_render',frame=end)


def camera_motion(cam,start,end,shot,move):
    cam.location=(0,-12,3.2); look_at(cam,(0,0,1.9)); cam.keyframe_insert('location',frame=start); cam.keyframe_insert('rotation_euler',frame=start)
    s=shot.lower(); m=move.lower()
    if 'close' in s: cam.location=(0,-8.8,2.75)
    elif 'wide' in s: cam.location=(0,-15,4.3)
    elif 'low' in s: cam.location=(0,-10,1.4)
    if 'left' in m: cam.location.x=-2.0
    elif 'right' in m: cam.location.x=2.0
    if 'orbit' in m: cam.rotation_euler.z=.12
    elif 'tilt' in m: cam.location.z += .7
    cam.keyframe_insert('location',frame=end); look_at(cam,(0,0,1.9)); cam.keyframe_insert('rotation_euler',frame=end)


def main():
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
    scene=bpy.context.scene
    try: scene.render.engine='BLENDER_EEVEE_NEXT'
    except Exception:
        try: scene.render.engine='BLENDER_EEVEE'
        except Exception: pass
    scene.render.resolution_x=W; scene.render.resolution_y=H; scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'; scene.render.image_settings.color_mode='RGB'; scene.render.fps=FPS
    scene.render.film_transparent=False
    try: scene.view_settings.look='AgX - Medium High Contrast'
    except Exception: pass
    scene.render.image_settings.color_mode='RGB'
    scene.render.filepath=OUT
    cam=camera_setup(); lights(); parts=character(); envs=[]
    for i,s in enumerate(SCENES,1): envs.append(environment(s['theme'],i))
    total=len(SCENES)*int(DUR*FPS); scene.frame_start=1; scene.frame_end=total
    for i,s in enumerate(SCENES,1):
        start=(i-1)*int(DUR*FPS)+1; end=i*int(DUR*FPS)
        set_world(s['theme']); visibility(envs,envs[i-1],start,end)
        animate(parts,start,end,s['emotion'],s['action']); camera_motion(cam,start,end,s['shot'],s['camera'])
    bpy.ops.wm.save_as_mainfile(filepath=OUT+'.blend')
    bpy.ops.render.render(animation=True)

main()
'''


def main() -> None:
    blender = blender_binary()
    if not blender:
        raise RuntimeError("Blender is required for the zero-dollar 3D engine")
    if not PLAN.exists():
        raise RuntimeError("director_plan.json is missing")
    plan = json.loads(PLAN.read_text(encoding='utf-8'))
    scenes = plan.get('scenes') or []
    if not scenes:
        raise RuntimeError("Director plan contains no scenes")
    scenes = scenes[:12]
    WORK.mkdir(parents=True, exist_ok=True)
    fps = int(os.getenv('3D_FPS','12'))
    width = int(os.getenv('3D_WIDTH','540'))
    height = int(os.getenv('3D_HEIGHT','960'))
    frames_pattern = WORK / 'frame_#####'
    with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False, encoding='utf-8') as fh:
        fh.write(make_script(scenes,fps,width,height,str(frames_pattern)))
        script=fh.name
    try:
        subprocess.run([blender,'--background','--python',script],check=True,cwd=ROOT)
        frames=WORK/'frame_%05d.png'
        if not list(WORK.glob('frame_*.png')):
            raise RuntimeError('Blender completed but produced no frames')
        subprocess.run(['ffmpeg','-y','-framerate',str(fps),'-i',str(frames),'-vf','scale=1080:1920:flags=lanczos,format=yuv420p','-c:v','libx264','-preset','veryfast','-crf','20','-an',str(FINAL)],check=True,cwd=ROOT)
        if not FINAL.exists() or FINAL.stat().st_size == 0:
            raise RuntimeError('3D animation encode produced no video')
        print(f'Richer zero-dollar 3D animation ready: {FINAL}')
    finally:
        Path(script).unlink(missing_ok=True)


if __name__=='__main__':
    main()
