"""Zero-dollar stylized 3D animation backend for normal videos.

This is deliberately separate from every existing kids-animation engine.
It uses Blender's free/open-source Python API to create a reusable stylized
character, a simple 3D environment, cinematic camera motion, facial/pose
acting and lighting. It is designed for CPU-safe GitHub Actions rendering.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
PLAN = OUTPUT / "normal_production" / "director_plan.json"
VOICE = OUTPUT / "voice.mp3"
WORK = OUTPUT / "normal_production" / "3d_animation"
FINAL = OUTPUT / "normal_production" / "3d-animation.mp4"


def blender_binary() -> str:
    return os.getenv("BLENDER_BIN") or shutil.which("blender") or ""


def scene_theme(text: str) -> str:
    t = text.lower()
    themes = {
        "ocean": ("ocean", "sea", "underwater", "shrimp", "whale", "fish"),
        "space": ("space", "planet", "star", "moon", "galaxy", "cosmic"),
        "forest": ("forest", "jungle", "tree", "bird", "frog", "insect"),
        "desert": ("desert", "sand", "boulder", "rock", "sahara"),
        "snow": ("snow", "ice", "arctic", "antarctica", "glacier", "polar"),
        "volcano": ("volcano", "lava", "eruption", "igneous"),
        "city": ("city", "street", "building", "traffic", "tokyo"),
    }
    for name, words in themes.items():
        if any(w in t for w in words):
            return name
    return "adventure"


def clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().replace("\\", "\\\\").replace("\"", "\\\"")


def build_blender_script(scenes: list[dict], fps: int, width: int, height: int, out_pattern: str) -> str:
    payload = json.dumps([
        {
            "n": i + 1,
            "text": clean_text(s.get("narration") or s.get("action") or s.get("visual_prompt")),
            "action": clean_text(s.get("action")),
            "emotion": clean_text(s.get("emotion")),
            "shot": clean_text(s.get("shot")),
            "camera": clean_text(s.get("camera_motion")),
            "theme": scene_theme(" ".join(str(s.get(k, "")) for k in ("narration", "subject", "location", "action", "visual_prompt"))),
        }
        for i, s in enumerate(scenes)
    ])
    return f'''import bpy, math, json, mathutils
from mathutils import Vector

SCENES = json.loads(r''' + repr(payload) + r''')
FPS = ''' + str(fps) + r'''
W, H = ''' + str(width) + ", " + str(height) + r'''
OUT = r''' + repr(out_pattern) + r'''

# ---------- materials ----------
def mat(name, color, metallic=0.0, rough=.48):
    m=bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color=(*color,1)
    m.use_nodes=True
    bs=m.node_tree.nodes.get('Principled BSDF')
    if bs:
        bs.inputs['Base Color'].default_value=(*color,1)
        bs.inputs['Roughness'].default_value=rough
        bs.inputs['Metallic'].default_value=metallic
    return m

BODY=mat('Character Body',(0.18,0.55,0.95),0,.38)
BELLY=mat('Character Belly',(0.92,0.72,0.36),0,.42)
DARK=mat('Eyes',(0.015,0.02,0.035),0,.2)
WHITE=mat('Eye White',(0.98,0.98,1),0,.18)
MOUTH=mat('Mouth',(0.16,0.025,0.03),0,.28)
GROUND=mat('Ground',(0.12,0.16,0.12),0,.85)
LEAF=mat('Leaf',(0.12,0.48,0.18),0,.7)
WATER=mat('Water',(0.04,0.30,0.58),0.05,.25)
SAND=mat('Sand',(0.72,0.47,0.25),0,.9)
SNOW=mat('Snow',(0.86,0.92,0.98),0,.7)
LAVA=mat('Lava',(0.9,0.15,0.025),0,.3)
SPACE=mat('Space',(0.008,0.012,0.035),0,.9)
GLOW=mat('Glow',(0.15,0.65,1.0),.05,.18)


def clear():
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
    for d in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        pass


def uv(name, loc, scale, material, seg=32, rings=16):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=rings, location=loc)
    o=bpy.context.object; o.name=name; o.scale=scale; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    o.data.materials.append(material); bpy.ops.object.shade_smooth(); return o


def ico(name, loc, scale, material, sub=2):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=sub, location=loc)
    o=bpy.context.object; o.name=name; o.scale=scale; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(material); bpy.ops.object.shade_smooth(); return o


def cyl(name, loc, radius, depth, material, rot=(0,0,0), verts=24):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=radius, depth=depth, location=loc, rotation=rot)
    o=bpy.context.object; o.name=name; o.data.materials.append(material); bpy.ops.object.shade_smooth(); return o


def cone(name, loc, r1, r2, depth, material):
    bpy.ops.mesh.primitive_cone_add(vertices=24, radius1=r1, radius2=r2, depth=depth, location=loc)
    o=bpy.context.object; o.name=name; o.data.materials.append(material); bpy.ops.object.shade_smooth(); return o


def create_character():
    root=bpy.data.objects.new('CHARACTER_ROOT',None); bpy.context.collection.objects.link(root)
    body=uv('Body',(0,0,1.65),(0.72,0.52,0.92),BODY); body.parent=root
    belly=uv('Belly',(0,-0.49,1.48),(0.43,0.08,0.52),BELLY); belly.parent=root
    head=uv('Head',(0,-0.01,2.65),(0.78,0.64,0.66),BODY); head.parent=root
    for x in (-0.27,0.27):
        eye=uv('Eye',(x,-0.59,2.78),(0.19,0.08,0.22),WHITE); eye.parent=root
        pupil=uv('Pupil',(x,-0.665,2.78),(0.075,0.035,0.10),DARK); pupil.parent=root
    mouth=uv('Mouth',(0,-0.67,2.47),(0.18,0.035,0.09),MOUTH); mouth.parent=root
    for x in (-0.78,0.78):
        arm=cyl('Arm',(x,0,1.65),0.16,0.9,BODY,rot=(0,math.pi/2,0)); arm.parent=root
    for x in (-0.32,0.32):
        leg=cyl('Leg',(x,0,0.72),0.19,0.75,BODY); leg.parent=root
        foot=uv('Foot',(x,-0.16,0.34),(0.27,0.38,0.16),DARK); foot.parent=root
    for x in (-0.42,0.42):
        ear=cone('Ear',(x,0,3.22),0.22,0,0.42,BODY); ear.parent=root
    return root


def add_tree(x,y,z,scale=1):
    trunk=cyl('TreeTrunk',(x,y,z+1.2),.22,2.4,SAND); trunk.scale=(scale,scale,scale)
    for dz,sz in ((2.3,.85),(3.0,.68),(3.5,.48)):
        uv('TreeCanopy',(x,y,z+dz),(sz*scale,sz*scale,sz*scale),LEAF)


def build_environment(theme):
    if theme=='ocean':
        floor=cyl('Ocean',(0,1,-.1),8,.2,WATER)
        for x in (-3,-1.2,1.4,3.2):
            cone('Coral',(x,1,.7),.35,.05,1.5,LEAF)
    elif theme=='forest':
        bpy.ops.mesh.primitive_plane_add(size=30, location=(0,1,0)); bpy.context.object.data.materials.append(GROUND)
        for x,y in [(-4,3),(-2,6),(3,5),(4,2),(-5,0)]: add_tree(x,y,0,.9)
    elif theme=='desert':
        bpy.ops.mesh.primitive_plane_add(size=30, location=(0,1,0)); bpy.context.object.data.materials.append(SAND)
        for x,y,s in [(-3,4,1),(3,5,.8),(4,1,1.2)]: ico('Boulder',(x,y,.5),(s,s*.8,s*.7),SAND,2)
    elif theme=='snow':
        bpy.ops.mesh.primitive_plane_add(size=30, location=(0,1,0)); bpy.context.object.data.materials.append(SNOW)
        for x,y in [(-4,4),(3,5),(4,1)]: cone('SnowPeak',(x,y,1.3),1.3,0,2.6,SNOW)
    elif theme=='volcano':
        bpy.ops.mesh.primitive_plane_add(size=30, location=(0,1,0)); bpy.context.object.data.materials.append(GROUND)
        cone('Volcano',(2,4,1.8),2.6,.5,3.6,GROUND); uv('Lava',(2,3.9,3.35),(.6,.6,.14),LAVA)
    elif theme=='space':
        bpy.ops.mesh.primitive_plane_add(size=30, location=(0,1,0)); bpy.context.object.data.materials.append(SPACE)
        for x,y,z in [(-4,4,5),(4,6,4),(3,2,6),(-3,0,5)]: uv('Star',(x,y,z),(.08,.08,.08),GLOW,16,8)
        uv('Planet',(3,5,2),(1.6,1.6,1.6),GLOW)
    elif theme=='city':
        bpy.ops.mesh.primitive_plane_add(size=30, location=(0,1,0)); bpy.context.object.data.materials.append(GROUND)
        for x in (-4,-2,2,4):
            bpy.ops.mesh.primitive_cube_add(size=1, location=(x,5,1.8)); o=bpy.context.object; o.scale=(1.1,1.2,1.8); o.data.materials.append(BODY)
    else:
        bpy.ops.mesh.primitive_plane_add(size=30, location=(0,1,0)); bpy.context.object.data.materials.append(GROUND)
        add_tree(-4,4,0,.8); add_tree(4,5,0,.7)


def setup_camera():
    bpy.ops.object.camera_add(location=(0,-12,3.2)); cam=bpy.context.object; bpy.context.scene.camera=cam
    cam.data.lens=52
    return cam


def look_at(obj, point):
    direction=Vector(point)-obj.location; obj.rotation_euler=direction.to_track_quat('-Z','Y').to_euler()


def setup_lights():
    bpy.ops.object.light_add(type='AREA', location=(-4,-5,7)); key=bpy.context.object; key.data.energy=850; key.data.shape='DISK'; key.data.size=5
    look_at(key,(0,0,1.8))
    bpy.ops.object.light_add(type='AREA', location=(4,-2,4)); fill=bpy.context.object; fill.data.energy=450; fill.data.size=4; look_at(fill,(0,0,2))
    bpy.ops.object.light_add(type='POINT', location=(0,3,5)); rim=bpy.context.object; rim.data.energy=350; rim.data.color=(.35,.65,1)


def animate_character(root, start, end, emotion, action):
    root.location=(0,0,0); root.rotation_euler=(0,0,0); root.keyframe_insert('location',frame=start); root.keyframe_insert('rotation_euler',frame=start)
    mid=(start+end)//2
    act=(action+' '+emotion).lower()
    if any(k in act for k in ('walk','run','move','travel','approach')):
        root.location.x=-1.2; root.rotation_euler.z=-.12; root.keyframe_insert('location',frame=start); root.keyframe_insert('rotation_euler',frame=start)
        root.location.x=1.0; root.rotation_euler.z=.12; root.keyframe_insert('location',frame=mid); root.keyframe_insert('rotation_euler',frame=mid)
        root.location.x=.2; root.rotation_euler.z=0; root.keyframe_insert('location',frame=end); root.keyframe_insert('rotation_euler',frame=end)
    elif any(k in act for k in ('look','watch','see','discover','surprise','shock')):
        root.rotation_euler.z=.22; root.keyframe_insert('rotation_euler',frame=mid)
        root.rotation_euler.z=-.18; root.keyframe_insert('rotation_euler',frame=end)
    elif any(k in act for k in ('jump','excited','celebrate')):
        root.location.z=.75; root.keyframe_insert('location',frame=mid)
        root.location.z=0; root.keyframe_insert('location',frame=end)
    else:
        root.location.z=.12; root.keyframe_insert('location',frame=mid); root.location.z=0; root.keyframe_insert('location',frame=end)
    for fc in root.animation_data.action.fcurves if root.animation_data and root.animation_data.action else []:
        for kp in fc.keyframe_points: kp.interpolation='BEZIER'


def render_scene(scene, idx, root, cam, fps):
    s=bpy.context.scene
    start=(idx-1)*int(2.6*fps)+1; end=idx*int(2.6*fps)
    theme=scene['theme']; build_environment(theme)
    animate_character(root,start,end,scene['emotion'],scene['action'])
    # cinematic camera move: push/pan/reveal based on director language
    cam.location=(0,-12,3.2); look_at(cam,(0,0,1.9)); cam.keyframe_insert('location',frame=start); cam.keyframe_insert('rotation_euler',frame=start)
    if 'wide' in scene['shot'].lower():
        cam.location=(0,-14,4.4)
    elif 'close' in scene['shot'].lower():
        cam.location=(0,-9,2.8)
    elif 'low' in scene['shot'].lower():
        cam.location=(0,-10,1.5)
    if 'left' in scene['camera'].lower(): cam.location.x=-2
    elif 'right' in scene['camera'].lower(): cam.location.x=2
    cam.keyframe_insert('location',frame=end); look_at(cam,(0,0,1.9)); cam.keyframe_insert('rotation_euler',frame=end)

    world=s.world
    world.color=(0.015,0.02,0.04)
    if theme=='ocean': world.color=(0.015,0.08,0.18)
    elif theme=='forest': world.color=(0.03,0.09,0.04)
    elif theme=='desert': world.color=(0.16,0.08,0.035)
    elif theme=='snow': world.color=(0.13,0.18,0.25)
    elif theme=='volcano': world.color=(0.12,0.015,0.008)
    elif theme=='space': world.color=(0.002,0.004,0.015)
    elif theme=='city': world.color=(0.035,0.045,0.08)


def main():
    clear()
    scene=bpy.context.scene
    scene.render.engine='BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in [i.identifier for i in scene.bl_rna.properties['render'].fixed_type.properties['engine'].enum_items] else scene.render.engine
    scene.render.resolution_x=W; scene.render.resolution_y=H; scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'; scene.render.film_transparent=False
    scene.render.fps=FPS
    scene.render.image_settings.color_mode='RGB'
    scene.view_settings.look='AgX - Medium High Contrast' if 'AgX - Medium High Contrast' in [i.name for i in bpy.types.ColorManagedViewSettings.bl_rna.properties['look'].enum_items] else scene.view_settings.look
    cam=setup_camera(); setup_lights(); root=create_character()
    total=max(1,len(SCENES))*int(2.6*FPS); scene.frame_start=1; scene.frame_end=total
    for i,s in enumerate(SCENES,1): render_scene(s,i,root,cam,FPS)
    scene.render.filepath=OUT
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
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    scenes = plan.get("scenes") or []
    if not scenes:
        raise RuntimeError("Director plan contains no scenes")
    WORK.mkdir(parents=True, exist_ok=True)
    fps = int(os.getenv("3D_FPS", "12"))
    width = int(os.getenv("3D_WIDTH", "540"))
    height = int(os.getenv("3D_HEIGHT", "960"))
    frames_pattern = WORK / "frame_#####"
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as fh:
        fh.write(build_blender_script(scenes, fps, width, height, str(frames_pattern)))
        script = fh.name
    try:
        subprocess.run([blender, "--background", "--python", script], check=True, cwd=ROOT)
        frames = WORK / "frame_%05d.png"
        if not list(WORK.glob("frame_*.png")):
            raise RuntimeError("Blender completed but produced no frames")
        subprocess.run([
            "ffmpeg", "-y", "-framerate", str(fps), "-i", str(frames),
            "-vf", "scale=1080:1920:flags=lanczos,format=yuv420p",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-an", str(FINAL)
        ], check=True, cwd=ROOT)
        print(f"Zero-dollar 3D animation ready: {FINAL}")
    finally:
        Path(script).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
