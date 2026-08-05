from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import subprocess

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
ASSETS = ROOT / "assets"
OUTPUT.mkdir(exist_ok=True)
ASSETS.mkdir(exist_ok=True)

W, H, FPS, SECONDS = 1080, 1920, 30, 6


def make_frame(index: int):
    img = Image.new("RGB", (W, H), (12, 12, 18))
    draw = ImageDraw.Draw(img)
    try:
        font_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 42)
    except OSError:
        font_big = font_small = ImageFont.load_default()

    title = "AI VIDEO AUTOMATION"
    subtitle = "Your first automated video"
    draw.text((W // 2, H // 2 - 100), title, font=font_big, anchor="mm")
    draw.text((W // 2, H // 2 + 20), subtitle, font=font_small, anchor="mm")
    draw.text((W // 2, H - 120), f"Frame {index + 1}", font=font_small, anchor="mm")
    return img


def main():
    frames = ASSETS / "frames"
    frames.mkdir(exist_ok=True)
    total = FPS * SECONDS

    for i in range(total):
        make_frame(i).save(frames / f"frame_{i:04d}.png")

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
