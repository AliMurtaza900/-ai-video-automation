from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import subprocess
import textwrap

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
ASSETS = ROOT / "assets"
VISUALS = ASSETS / "visuals"
OUTPUT.mkdir(exist_ok=True)
ASSETS.mkdir(exist_ok=True)

W, H, FPS = 1080, 1920, 30
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def get_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def media_duration(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return max(1.0, float(result.stdout.strip()))


def load_caption_timings():
    timing_file = OUTPUT / "caption_timing.txt"
    if not timing_file.exists():
        return []
    result = []
    for line in timing_file.read_text(encoding="utf-8").splitlines():
        try:
            start, end, text = line.split("|", 2)
            result.append((float(start), float(end), text.strip()))
        except ValueError:
            continue
    return result


def caption_for_time(timings, t):
    for i, (start, end, text) in enumerate(timings):
        if start <= t < end:
            return text, i, start, end
    return "", -1, 0, 0


def load_visuals():
    images = []
    for path in sorted(VISUALS.glob("visual_*")):
        try:
            images.append(Image.open(path).convert("RGB"))
        except OSError:
            pass
    return images


def prepare_visual(image):
    scale = max(W / image.width, H / image.height) * 1.10
    nw, nh = int(image.width * scale), int(image.height * scale)
    return image.resize((nw, nh), Image.Resampling.LANCZOS)


def visual_background(images, scene_index, scene_progress):
    if not images:
        p = (scene_index * 0.17 + scene_progress) % 1.0
        return Image.new("RGB", (W, H), (int(8 + 18 * p), int(12 + 15 * (1 - p)), 28))

    image = prepare_visual(images[scene_index % len(images)])
    max_left = max(0, image.width - W)
    max_top = max(0, image.height - H)
    x = scene_progress if scene_index % 2 == 0 else 1.0 - scene_progress
    y = 0.25 + 0.35 * ((scene_index * 0.37) % 1.0)
    left = int(max_left * x)
    top = int(max_top * y)
    image = image.crop((left, top, left + W, top + H))

    blurred = image.filter(ImageFilter.GaussianBlur(12)).convert("RGBA")
    base = Image.blend(blurred.convert("RGB"), image, 0.88).convert("RGBA")
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for y in range(H):
        edge = min(y, H - y) / (H / 2)
        vignette = int(max(0, 70 * (1 - edge)))
        lower = int(80 * max(0, (y - H * 0.48) / (H * 0.52)))
        od.line((0, y, W, y), fill=(0, 0, 0, min(145, vignette + lower)))
    return Image.alpha_composite(base, overlay).convert("RGB")


def draw_caption(img, caption, progress):
    if not caption:
        return
    draw = ImageDraw.Draw(img)
    font = get_font(FONT_BOLD, 66 if len(caption) < 48 else 56)
    wrapped = "\n".join(textwrap.wrap(caption, width=25))
    bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=10, align="center")
    pad_x, pad_y = 48, 34
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    pulse = 0.97 + min(1.0, progress * 5) * 0.03
    bw, bh = int((w + 2 * pad_x) * pulse), int((h + 2 * pad_y) * pulse)
    box = (W // 2 - bw // 2, H // 2 - bh // 2, W // 2 + bw // 2, H // 2 + bh // 2)
    draw.rounded_rectangle(box, radius=38, fill=(3, 6, 15, 205), outline=(255, 255, 255), width=3)
    draw.multiline_text((W // 2, H // 2), wrapped, font=font, spacing=10, align="center", anchor="mm", fill=(255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0))


def make_frame(index, timings, visuals, duration):
    t = index / FPS
    caption, scene_index, start, end = caption_for_time(timings, t)
    scene_progress = 0.0 if end <= start else (t - start) / (end - start)
    img = visual_background(visuals, max(scene_index, 0), scene_progress)
    draw = ImageDraw.Draw(img)

    title_font = get_font(FONT_BOLD, 44)
    small_font = get_font(FONT_BOLD, 28)

    draw.rounded_rectangle((34, 34, 278, 98), radius=28, fill=(0, 0, 0, 145), outline=(255, 255, 255), width=2)
    draw.text((156, 66), "AI FACTS", font=title_font, anchor="mm", fill=(255, 255, 255))

    progress = min(1.0, t / duration)
    draw.rounded_rectangle((45, 116, W - 45, 126), radius=5, fill=(55, 55, 55))
    draw.rounded_rectangle((45, 116, 45 + int((W - 90) * progress), 126), radius=5, fill=(255, 255, 255))

    if caption:
        draw_caption(img, caption, scene_progress)

    if t >= max(0, duration - 2.5):
        cta = "FOLLOW FOR MORE"
        bbox = draw.textbbox((0, 0), cta, font=small_font)
        pad = 24
        draw.rounded_rectangle((W // 2 - (bbox[2] - bbox[0]) // 2 - pad, H - 145, W // 2 + (bbox[2] - bbox[0]) // 2 + pad, H - 78), radius=25, fill=(0, 0, 0, 185), outline=(255, 255, 255), width=2)
        draw.text((W // 2, H - 112), cta, font=small_font, anchor="mm", fill=(255, 255, 255))

    return img


def main():
    script_file = OUTPUT / "script.txt"
    voice_file = OUTPUT / "voice.mp3"
    script = script_file.read_text(encoding="utf-8").strip() if script_file.exists() else ""
    if not script:
        raise RuntimeError("Generated script is empty")
    if not voice_file.exists():
        raise RuntimeError("Voice file is missing; generate the voice before rendering")

    timings = load_caption_timings()
    if not timings:
        raise RuntimeError("Caption timing data is missing; generate the voice before rendering")

    duration = media_duration(voice_file)
    visuals = load_visuals()
    print(f"Using {len(visuals)} visuals for {duration:.2f}s narration")

    frames = ASSETS / "frames"
    frames.mkdir(exist_ok=True)
    total = max(1, int(duration * FPS) + 1)
    for old in frames.glob("frame_*.png"):
        old.unlink()

    for i in range(total):
        make_frame(i, timings, visuals, duration).save(frames / f"frame_{i:05d}.png")

    output = OUTPUT / "test-video.mp4"
    subprocess.run(["ffmpeg", "-y", "-framerate", str(FPS), "-i", str(frames / "frame_%05d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-vf", "scale=1080:1920", "-movflags", "+faststart", str(output)], check=True)
    print(f"Created {output}")


if __name__ == "__main__":
    main()
