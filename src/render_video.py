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
            return text, start, end
    return "", 0, 0


def load_visuals():
    images = []
    for path in sorted(VISUALS.glob("visual_*")):
        try:
            images.append(Image.open(path).convert("RGB"))
        except OSError:
            pass
    return images


def fit_cover(image):
    scale = max(W / image.width, H / image.height) * 1.08
    nw, nh = int(image.width * scale), int(image.height * scale)
    image = image.resize((nw, nh), Image.Resampling.LANCZOS)
    return image


def visual_background(images, index):
    if not images:
        return Image.new("RGB", (W, H), (12, 16, 28))

    # Faster scene changes keep the Short visually active.
    slot = max(1, FPS * 3)
    image = fit_cover(images[(index // slot) % len(images)])
    progress = (index % slot) / slot
    max_left = max(0, image.width - W)
    max_top = max(0, image.height - H)
    left = int(max_left * (0.15 + 0.7 * progress))
    top = int(max_top * (0.75 - 0.45 * progress))
    image = image.crop((left, top, left + W, top + H))

    # Cinematic treatment: blur a copy behind the main image, then add a
    # readable dark gradient without hiding the actual subject.
    blurred = image.filter(ImageFilter.GaussianBlur(14)).convert("RGBA")
    base = Image.alpha_composite(blurred, image.convert("RGBA"))
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for y in range(H):
        strength = int(35 + 115 * (y / H))
        od.line((0, y, W, y), fill=(0, 0, 0, strength))
    return Image.alpha_composite(base, overlay).convert("RGB")


def draw_center_caption(img, caption, active):
    if not caption:
        return
    draw = ImageDraw.Draw(img)
    font = get_font(FONT_BOLD, 68 if len(caption) < 55 else 58)
    wrapped = "\n".join(textwrap.wrap(caption, width=25))
    bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=10, align="center")
    pad_x, pad_y = 48, 34
    box = (
        W // 2 - (bbox[2] - bbox[0]) // 2 - pad_x,
        H // 2 - (bbox[3] - bbox[1]) // 2 - pad_y,
        W // 2 + (bbox[2] - bbox[0]) // 2 + pad_x,
        H // 2 + (bbox[3] - bbox[1]) // 2 + pad_y,
    )
    # Slight pulse on every caption change.
    expand = int(5 * active)
    box = (box[0] - expand, box[1] - expand, box[2] + expand, box[3] + expand)
    draw.rounded_rectangle(box, radius=38, fill=(3, 6, 15, 205), outline=(255, 255, 255), width=3)
    draw.multiline_text(
        (W // 2, H // 2), wrapped, font=font, spacing=10,
        align="center", anchor="mm", fill=(255, 255, 255),
        stroke_width=2, stroke_fill=(0, 0, 0)
    )


def make_frame(index, timings, visuals):
    img = visual_background(visuals, index)
    draw = ImageDraw.Draw(img)
    t = index / FPS

    title_font = get_font(FONT_BOLD, 48)
    small_font = get_font(FONT_BOLD, 30)
    badge_font = get_font(FONT_BOLD, 28)

    # Top branding bar.
    draw.rounded_rectangle((34, 34, 300, 105), radius=30, fill=(0, 0, 0, 165), outline=(255, 255, 255), width=2)
    draw.text((167, 69), "AI FACTS", font=title_font, anchor="mm", fill=(255, 255, 255))

    # Progress bar helps retention and makes the video feel intentionally edited.
    progress = min(1.0, t / MAX_SECONDS)
    draw.rounded_rectangle((50, 124, W - 50, 134), radius=5, fill=(40, 40, 40))
    draw.rounded_rectangle((50, 124, 50 + int((W - 100) * progress), 134), radius=5, fill=(255, 255, 255))

    caption, start, end = caption_for_frame(timings, index)
    if caption:
        active = min(1.0, max(0.0, (t - start) * 6))
        draw_center_caption(img, caption, active)

    # Short CTA only appears at the end instead of permanently occupying the frame.
    if t >= min(MAX_SECONDS - 3, 38):
        cta = "FOLLOW FOR MORE"
        bbox = draw.textbbox((0, 0), cta, font=small_font)
        pad = 26
        draw.rounded_rectangle(
            (W // 2 - (bbox[2] - bbox[0]) // 2 - pad, H - 150,
             W // 2 + (bbox[2] - bbox[0]) // 2 + pad, H - 78),
            radius=28, fill=(0, 0, 0, 190), outline=(255, 255, 255), width=2
        )
        draw.text((W // 2, H - 114), cta, font=small_font, anchor="mm", fill=(255, 255, 255))

    # Subtle timestamp marker gives the bottom edge a finished editorial look.
    draw.text((W - 42, H - 40), f"{int(t):02d}s", font=badge_font, anchor="rs", fill=(255, 255, 255))
    return img


def main():
    script_file = OUTPUT / "script.txt"
    script = script_file.read_text(encoding="utf-8").strip() if script_file.exists() else ""
    if not script:
        raise RuntimeError("Generated script is empty")

    timings = load_caption_timings()
    if not timings:
        raise RuntimeError("Caption timing data is missing; generate the voice before rendering")

    visuals = load_visuals()
    print(f"Using {len(visuals)} downloaded visuals")

    frames = ASSETS / "frames"
    frames.mkdir(exist_ok=True)
    total = FPS * MAX_SECONDS
    for old in frames.glob("frame_*.png"):
        old.unlink()

    for i in range(total):
        make_frame(i, timings, visuals).save(frames / f"frame_{i:04d}.png")

    output = OUTPUT / "test-video.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-framerate", str(FPS),
        "-i", str(frames / "frame_%04d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-vf", "scale=1080:1920",
        str(output)
    ], check=True)
    print(f"Created {output}")


if __name__ == "__main__":
    main()
