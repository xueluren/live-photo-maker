# live-photo-maker

Turn any **JPG + MOV/MP4 pair** into a real **Apple Live Photo** — on Linux,
Windows, or macOS, with no Apple frameworks and no third-party app.

把任意 **JPG + 视频** 变成真正的 **Apple Live Photo（实况照片）**，跨平台，
不需要 Mac、不需要 intoLive 这类 App。

Most "video to Live Photo" tools either need a Mac (Core Graphics /
AVFoundation) or an iPhone app. This one writes the pairing metadata by hand,
at the byte level, in pure Python + ffmpeg:

- **Still (JPG)** — an Apple MakerNote (EXIF `0x927C`) whose tag `0x0011`
  holds the asset UUID:
  `"Apple iOS\0" + 0x0001 + "MM" + IFD(1 entry) + <uuid>\0`, with value
  offsets relative to the start of the maker note (UUID at `0x20`).
  The image pixels are **never re-encoded**.
- **Video (MOV)** — the pairing keys go into **`moov/meta`** (a plain
  container box with `hdlr(mdta)` + `keys` + `ilst`):
  `com.apple.quicktime.content.identifier` = the same UUID, plus
  `com.apple.quicktime.live-photo.auto = 1` and
  `com.apple.quicktime.full-frame-rate-playback-intent = 1`.
  The video stream is **stream-copied, never re-encoded**.
  > ⚠️ `ffmpeg -metadata …` alone does **not** work: it writes
  > `moov/udta/meta`, which AVFoundation does not read for pairing — tools
  > like ExifTool report both locations identically, so the mistake is easy
  > to miss. This was the single most expensive bug in this format.
- **`.pvt` package (optional)** — a `<name>.pvt/` folder containing the
  paired `.jpg` + `.mov` and a `metadata.plist` whose only key is
  `PFVideoComplementMetadataVersionKey = "1"` (the layout used by
  [makelive](https://github.com/RhetTbull/makelive)).

## Prefer it on your iPhone instead? (no intoLive)

The [`ios/`](ios/) folder contains **LiveMaker**, a small SwiftUI app that
does the whole job on the phone itself — pick a still image, add an
animation effect (snow / sparkles / slow zoom, rendered on-device, the
image is never AI-redrawn), or pick a video, and save a genuine Live Photo
straight into your photo library via PhotoKit. Free to install with Xcode
and a personal Apple ID; see [`ios/README.md`](ios/README.md).

## Requirements (CLI)

- Python 3.9+
- [ffmpeg](https://ffmpeg.org/) on your `PATH`
- `piexif` — `pip install -r requirements.txt`

## Usage

```bash
# make a Live Photo pair (+ .pvt package)
python3 livephoto.py make --image cover.jpg --video clip.mp4 \
    --outdir out --name my-live-photo --pvt

# verify a pair: both ContentIdentifiers must match
python3 livephoto.py check out/my-live-photo.jpg out/my-live-photo.mov
# -> PAIR OK
```

`make` generates a fresh uppercase UUID, writes it into both files, and runs
the same check before reporting success. Output is `NAME.jpg` + `NAME.mov`
(plus `NAME.pvt/` with `--pvt`).

## Getting it onto an iPhone

- **With a Mac:** unzip if needed, drag the `.pvt` folder (or the JPG+MOV
  pair together) into Apple Photos — it imports as **one** Live Photo.
  iCloud Photos then syncs it to your iPhone, or AirDrop the Live Photo
  from Photos (share the asset, not the raw files). Set it as wallpaper
  from Photos.
- **iPhone only:** loose JPG+MOV files saved separately do **not** pair in
  iOS Photos — that final step still needs an on-device app or the Mac
  route above. This is an iOS limitation, not a file problem.

## Status / 已知状态

- Pair generation is verified locally two independent ways: a from-scratch
  parser (following ExifTool's documented MakerNote offsets) and ffprobe,
  which reads the `content.identifier` back out of `moov/meta`.
- End-to-end import on a real device is still being collected — if you try
  it, please open an issue with your iOS/macOS version and what Photos did
  with the pair. Reports help everyone.
- No `still-image-time` (`mebx`) timed-metadata track is written: phone
  samples verified in the references work without one, and the still used
  here is the video's poster frame.

## References

Format details were worked out from these open-source projects — thank you:

- [RhetTbull/makelive](https://github.com/RhetTbull/makelive) — pairing
  rules and the `.pvt` package layout.
- [LivePhotoTools `docs/FORMATS.md`](https://github.com/reviventura/LivePhotoTools/blob/HEAD/docs/FORMATS.md)
  — byte-level MakerNote and `moov/meta` layouts, verified against files
  straight off a phone.
- Limit Point's [Live Photo format write-up](https://www.limit-point.com/blog/live-photos).

## License

MIT — see [LICENSE](LICENSE).
