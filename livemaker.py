#!/usr/bin/env python3
"""
livemaker.py — Live Maker, installed in Muse.

One command turns a still image into finished moving-photo products:
  livemaker.py make --image IMG --effect snow|sparkles|zoom|snowzoom|none \
      [--duration 5] [--fps 30] --outdir OUT --name NAME
  livemaker.py from-video --video VID [--image COVER] --outdir OUT --name NAME

Animation is composited over the original image (never AI-redrawn, original
resolution preserved). Outputs in OUT:
  NAME.mp4          the animation itself (preview / sharing)
  NAME.jpg + NAME.mov   Apple Live Photo pair (shared UUID, see livephoto.py)
  NAME.pvt/         makelive-style package of the pair
  NAME-motion.jpg   single-file Motion Photo JPEG (embedded MP4 + XMP)
Every run self-checks the pair before reporting success.
"""
import argparse, math, os, random, shutil, subprocess, sys, uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import livephoto as lp
import motion_jpeg
from PIL import Image, ImageDraw, ImageFilter
import numpy as np

# ------------------------------------------------------------------ sprites
def soft_dot(r, alpha, color=(255, 255, 255)):
    size = max(4, int(r * 4))
    y, x = np.mgrid[0:size, 0:size]
    c = size / 2.0
    dist = np.sqrt((x - c + 0.5) ** 2 + (y - c + 0.5) ** 2) / r
    a = np.clip(1.0 - dist, 0, 1) ** 0.9
    arr = np.zeros((size, size, 4), dtype=np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = color
    arr[..., 3] = (a * alpha).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")

def star_sprite(R, alpha):
    s = int(R * 2 + 4)
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = cy = s / 2
    pts = []
    for k in range(8):
        ang = -math.pi / 2 + k * math.pi / 4
        r = R if k % 2 == 0 else R * 0.16
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    d.polygon(pts, fill=(255, 255, 255, alpha))
    d.ellipse([cx - R * 0.16, cy - R * 0.16, cx + R * 0.16, cy + R * 0.16],
              fill=(255, 255, 255, alpha))
    return img.filter(ImageFilter.GaussianBlur(R * 0.06 + 0.6))

# ------------------------------------------------------------------ animate
def animate(image_path, effect, duration, fps, out_mp4):
    base = Image.open(image_path).convert("RGB")
    W, H = base.size
    frames = int(duration * fps)
    scale = (W * H) / (1080 * 1920)
    random.seed(7)
    margin = 48
    travel = H + 2 * margin

    flakes = []
    if effect in ("snow", "snowzoom"):
        def add(count, rmin, rmax, k, amin, amax):
            for _ in range(int(count * max(scale, 0.35))):
                r = random.uniform(rmin, rmax) * (1 + 0.3 * (scale - 1))
                fl = {"x": random.uniform(0, W), "y": random.uniform(0, travel),
                      "r": r, "k": k,
                      "sway": random.uniform(8, 30),
                      "cyc": random.choice([1, 2, 3]),
                      "ph": random.uniform(0, 2 * math.pi),
                      "a": random.randint(amin, amax)}
                fl["w"] = soft_dot(r, fl["a"])
                fl["s"] = soft_dot(r * 1.15, int(fl["a"] * 0.38), (165, 185, 210))
                flakes.append(fl)
        add(300, 1.4, 3.0, 1, 150, 210)
        add(210, 3.0, 6.5, 2, 180, 235)
        add(85, 6.5, 13.0, 3, 205, 255)

    sparkles = []
    star_cache = {}
    if effect == "sparkles":
        for _ in range(int(36 * max(scale, 0.5))):
            sparkles.append({"x": random.uniform(20, W - 20), "y": random.uniform(20, H - 20),
                             "r": random.uniform(8, 30),
                             "ph": random.uniform(0, 2 * math.pi),
                             "max": random.randint(120, 230),
                             "cyc": random.choice([2, 3, 4])})
    def get_star(r, a):
        key = (round(r), (a // 16) * 16)
        if key not in star_cache:
            star_cache[key] = star_sprite(max(6, int(r)), key[1])
        return star_cache[key]

    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(fps), "-i", "-", "-an", "-c:v", "libx264",
           "-pix_fmt", "yuv420p", "-crf", "16", "-preset", "medium",
           "-movflags", "+faststart", out_mp4]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    base_arr = np.array(base)
    for i in range(frames):
        t = i / frames
        if effect in ("zoom", "snowzoom"):
            s = 1.0 + 0.08 * t
            zw, zh = round(W * s), round(H * s)
            frame = base.resize((zw, zh), Image.LANCZOS).crop(
                ((zw - W) // 2, (zh - H) // 2, (zw - W) // 2 + W, (zh - H) // 2 + H))
            frame = frame.convert("RGBA")
        else:
            frame = Image.fromarray(base_arr).convert("RGBA")
        if flakes:
            ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            for f in flakes:
                y = (f["y"] + f["k"] * travel * t) % travel - margin
                x = f["x"] + math.sin(2 * math.pi * f["cyc"] * t + f["ph"]) * f["sway"]
                ov.alpha_composite(f["s"], (int(x - f["s"].size[0] / 2 + 2), int(y - f["s"].size[1] / 2 + 3)))
                ov.alpha_composite(f["w"], (int(x - f["w"].size[0] / 2), int(y - f["w"].size[1] / 2)))
            frame.alpha_composite(ov)
        for sp in sparkles:
            s = 0.5 + 0.5 * math.sin(2 * math.pi * sp["cyc"] * t + sp["ph"])
            a = int(sp["max"] * s * s)
            if a < 8:
                continue
            spr = get_star(sp["r"] * (0.7 + 0.45 * s), a)
            frame.alpha_composite(spr, (int(sp["x"] - spr.size[0] / 2), int(sp["y"] - spr.size[1] / 2)))
        proc.stdin.write(np.array(frame.convert("RGB")).tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg render failed")

# ------------------------------------------------------------------ package
def package(image_path, video_mp4, outdir, name, make_pvt=True):
    os.makedirs(outdir, exist_ok=True)
    asset_id = str(uuid.uuid4()).upper()
    jpg_out = os.path.join(outdir, name + ".jpg")
    mov_out = os.path.join(outdir, name + ".mov")
    mp4_out = os.path.join(outdir, name + ".mp4")
    if os.path.abspath(video_mp4) != os.path.abspath(mp4_out):
        shutil.copy(video_mp4, mp4_out)
    lp.write_jpg(image_path, jpg_out, asset_id)
    lp.write_mov(mp4_out, mov_out, asset_id)
    ok = lp.cmd_check(jpg_out, mov_out, quiet=True)
    motion_out = os.path.join(outdir, name + "-motion.jpg")
    motion_jpeg.make(jpg_out, mp4_out, motion_out)
    pvt = None
    if make_pvt:
        pvt = os.path.join(outdir, name + ".pvt")
        os.makedirs(pvt, exist_ok=True)
        shutil.copy(jpg_out, pvt)
        shutil.copy(mov_out, pvt)
        open(os.path.join(pvt, "metadata.plist"), "w").write(lp.PLIST)
    print(f"asset_id={asset_id}")
    print(f"video={mp4_out}")
    print(f"pair={jpg_out} + {mov_out}  check={'OK' if ok else 'FAILED'}")
    print(f"motion_jpeg={motion_out}")
    if pvt:
        print(f"pvt={pvt}")
    return 0 if ok else 1

def main():
    ap = argparse.ArgumentParser(prog="livemaker")
    sub = ap.add_subparsers(dest="cmd", required=True)
    mk = sub.add_parser("make")
    mk.add_argument("--image", required=True)
    mk.add_argument("--effect", default="zoom",
                    choices=["snow", "sparkles", "zoom", "snowzoom", "none"])
    mk.add_argument("--duration", type=float, default=5)
    mk.add_argument("--fps", type=int, default=30)
    mk.add_argument("--outdir", required=True)
    mk.add_argument("--name", required=True)
    fv = sub.add_parser("from-video")
    fv.add_argument("--video", required=True)
    fv.add_argument("--image", help="cover still; default: frame at 0.5s of the video")
    fv.add_argument("--outdir", required=True)
    fv.add_argument("--name", required=True)
    args = ap.parse_args()

    if args.cmd == "make":
        os.makedirs(args.outdir, exist_ok=True)
        render = os.path.join(args.outdir, args.name + ".mp4")
        if args.effect == "none":
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", args.image,
                            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16",
                            "-t", str(args.duration), "-r", str(args.fps), render], check=True)
        else:
            animate(args.image, args.effect, args.duration, args.fps, render)
        return package(args.image, render, args.outdir, args.name)

    # from-video
    cover = args.image
    if not cover:
        cover = os.path.join(args.outdir, "_cover.jpg")
        os.makedirs(args.outdir, exist_ok=True)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "0.5", "-i", args.video,
                        "-frames:v", "1", "-q:v", "2", cover], check=True)
    rc = package(cover, args.video, args.outdir, args.name)
    if not args.image and os.path.exists(cover):
        os.unlink(cover)
    return rc

if __name__ == "__main__":
    sys.exit(main())
