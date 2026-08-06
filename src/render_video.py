from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import subprocess
import textwrap

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
ASSETS = ROOT / "assets"
VISUALS = ASSETS / "visuals"
OUTPUT.mkdir(exist_ok=True)
ASSETS.mkdir(exist_ok=True)

W, H, FPS = 1080, 1920, 30
MAX_SECONDS = 45
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def get_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


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


def caption_for_frame(timings, frame):
    t = frame / FPS
    for start, end, text in timings:
        if start <= t < end:
            return text
    return ""


def load_visuals():
    images = []
    for path in sorted(VISUALS.glob("visual_*")):
        try:
            images.append(Image.open(path).convert("RGB"))
        except OSError:
            pass
    return images


def visual_background(images, index):
    if not images:
        phase = index / (FPS * 2)
        return Image.new("RGB", (W, H), (
            int(10 + 12 * (phase % 1)),
            int(14 + 10 * ((phase + 0.33) % 1)),
            int(28 + 18 * ((phase + 0.66) % 1)),
        ))

    slot = max(1, FPS * 5)
    image = images[(index // slot) % len(images)].copy()
    scale = max(W / image.width, H / image.height) * (1.0 + 0.08 * ((index % slot) / slot))
    nw, nh = int(image.width * scale), int(image.height * scale)
    image = image.resize((nw, nh), Image.Resampling.LANCZOS)
    left = max(0, (nw - W) // 2)
    top = max(0, (nh - H) // 2)
    return image.crop((left, top, left + W, top + H))


def make_frame(index, timings, visuals):
    img = visual_background(visuals, index)
    draw = ImageDraw.Draw(img)
    title_font = get_font(FONT_BOLD, 44)
    caption_font = get_font(FONT_BOLD, 62)
    small_font = get_font(FONT_BOLD, 28)

    draw.rounded_rectangle((34, 34, 278, 98), radius=28, fill=(0, 0, 0), outline=(255, 255, 255), width=2)
    draw.text((156, 66), "AI FACTS", font=title_font, anchor="mm", fill=(255, 255, 255))

    caption = caption_for_frame(timings, index)
    if caption:
        wrapped = "\n".join(textwrap.wrap(caption, width=25))
        bbox = draw.multiline_textbbox((0, 0), wrapped, font=caption_font, spacing=10, align="center")
        pad = 40
        box = (W // 2 - (bbox[2] - bbox[0]) // 2 - pad, H // 2 - (bbox[3] - bbox[1]) // 2 - pad, W // 2 + (bbox[2] - bbox[0]) // 2 + pad, H // 2 + (bbox[3] - bbox[1]) // 2 + pad)
        draw.rounded_rectangle(box, radius=32, fill=(5, 5, 10), outline=(255, 255, 255), width=3)
        draw.multiline_text((W // 2, H // 2), wrapped, font=caption_font, spacing=10, align="center", anchor="mm", fill=(255, 255, 255))

    draw.text((W // 2, H - 110), "Follow for more facts", font=small_font, anchor="mm", fill=(255, 255, 255))
    return img


def main():
    script = (OUTPUT / "script.txt").read_text(encoding="utf-8").strip() if (OUTPUT / "script.txt").exists() else ""
    if not script:
        raise RuntimeError("Generated script is empty")
    timings = load_caption_timings()
    if not timings:
        raise RuntimeError("Caption timing data is missing; generate the voice before rendering")
    visuals = load_visuals()
    frames = ASSETS / "frames"
    frames.mkdir(exist_ok=True)
    total = FPS * MAX_SECONDS
    for old in frames.glob("frame_*.png"):
        old.unlink()
    for i in range(total):
        make_frame(i, timings, visuals).save(frames / f"frame_{i:04d}.png")

    output = OUTPUT / "test-video.mp4"
    subprocess.run(["ffmpeg", "-y", "-framerate", str(FPS), "-i", str(frames / "frame_%04d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-vf", "scale=1080:1920", str(output)], check=True)
    print(f"Created {output}")


if __name__ == "__main__":
    main()
