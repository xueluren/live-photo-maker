#!/usr/bin/env python3
"""
livephoto.py — create Apple Live Photos from a JPG + MOV pair on any OS
(no macOS frameworks, no re-encoding of the still or the video stream).

Implements the pairing format verified against open-source references:
- Still (JPG): Apple MakerNote (EXIF 0x927C) holding tag 0x0011 = asset UUID.
  Layout per LivePhotoTools/docs/FORMATS.md (verified against a phone file):
      "Apple iOS\0" + 0x0001 + "MM" + IFD(1 entry) + <uuid>\0
  Value offsets are relative to the start of the maker note; UUID sits at 0x20.
  The JPEG pixel data is never re-encoded (byte-level EXIF patch via piexif).
- Video (MOV): movie-level metadata in moov/meta (plain container box,
  NOT moov/udta/meta — AVFoundation does not read pairing keys from udta):
      hdlr(mdta) + keys + ilst
  keys: com.android.version="16", com.apple.quicktime.content.identifier=<uuid>,
        com.apple.quicktime.live-photo.auto=uint8 1,
        com.apple.quicktime.full-frame-rate-playback-intent=int64 1
  Written by byte-level box surgery; the video stream is stream-copied only.
- Optional .pvt package per RhetTbull/makelive: <stem>.pvt/ containing the
  paired .jpg + .mov and a metadata.plist whose only key is
  PFVideoComplementMetadataVersionKey = "1".

Usage:
  livephoto.py make --image cover.jpg --video clip.mov --outdir OUT [--name NAME] [--pvt]
  livephoto.py check photo.jpg video.mov
"""
import argparse, os, shutil, struct, subprocess, sys, tempfile, uuid

_vendor = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor")
if os.path.isdir(_vendor):
    sys.path.insert(0, _vendor)
import piexif  # pip install piexif (see requirements.txt), or a vendored copy

MAKERNOTE_TAG = 37500  # 0x927C

# ---------------------------------------------------------------- still image
def build_makernote(asset_id: str) -> bytes:
    uuid_bytes = asset_id.encode("ascii") + b"\x00"          # 37 bytes
    note = bytearray()
    note += b"Apple iOS\x00"                                  # 10
    note += struct.pack(">H", 1)                              # 0x0001
    note += b"MM"                                             # 12..13
    note += struct.pack(">H", 1)                              # IFD entry count @14
    note += struct.pack(">HHI", 0x0011, 2, len(uuid_bytes))   # tag, ASCII, count
    note += struct.pack(">I", 0x20)                           # value offset @24..27
    note += struct.pack(">I", 0)                              # next IFD @28..31
    assert len(note) == 0x20, len(note)
    note += uuid_bytes                                        # @32
    return bytes(note)

def write_jpg(src: str, dst: str, asset_id: str) -> None:
    exif = piexif.load(src, key_is_name=False)
    exif.setdefault("Exif", {})[MAKERNOTE_TAG] = build_makernote(asset_id)
    piexif.insert(piexif.dump(exif), src, dst)

def read_jpg_id(path: str):
    exif = piexif.load(path, key_is_name=False)
    note = exif.get("Exif", {}).get(MAKERNOTE_TAG)
    if not note or not note.startswith(b"Apple iOS\x00"):
        return None
    count = struct.unpack(">H", note[14:16])[0]
    for i in range(count):
        off = 16 + i * 12
        tag, typ, cnt = struct.unpack(">HHI", note[off:off + 8])
        voff = struct.unpack(">I", note[off + 8:off + 12])[0]
        if tag == 0x0011:
            raw = note[voff:voff + cnt]
            return raw.split(b"\x00")[0].decode("ascii", "replace")
    return None

# ---------------------------------------------------------------- video (MOV)
def _box(data, off):
    size = struct.unpack(">I", data[off:off + 4])[0]
    typ = data[off + 4:off + 8].decode("latin1")
    hdr = 8
    if size == 1:
        size = struct.unpack(">Q", data[off + 8:off + 16])[0]; hdr = 16
    elif size == 0:
        size = len(data) - off
    return typ, size, hdr

def _children(data, start, end):
    out, off = [], start
    while off + 8 <= end:
        typ, size, hdr = _box(data, off)
        if size < hdr or off + size > end + 8:
            break
        out.append((typ, off, size, hdr))
        off += size
    return out

def build_meta_box(asset_id: str) -> bytes:
    keys = [
        ("com.android.version", 1, b"16"),
        ("com.apple.quicktime.content.identifier", 1, asset_id.encode("ascii")),
        ("com.apple.quicktime.live-photo.auto", 21, b"\x01"),
        ("com.apple.quicktime.full-frame-rate-playback-intent", 21, struct.pack(">q", 1)),
    ]
    hdlr = struct.pack(">I", 33) + b"hdlr" + b"\x00" * 8 + b"mdta" + b"\x00" * 12 + b"\x00"
    kb = struct.pack(">II", 0, len(keys))
    for name, _, _ in keys:
        kb += struct.pack(">I", 8 + len(name)) + b"mdta" + name.encode("ascii")
    keys_box = struct.pack(">I", 8 + len(kb)) + b"keys" + kb
    ilst = b""
    for idx, (_, dtype, value) in enumerate(keys, start=1):
        data_box = struct.pack(">I", 16 + len(value)) + b"data" + struct.pack(">II", dtype, 0) + value
        ilst += struct.pack(">I", 8 + len(data_box)) + struct.pack(">I", idx) + data_box
    ilst_box = struct.pack(">I", 8 + len(ilst)) + b"ilst" + ilst
    body = hdlr + keys_box + ilst_box
    return struct.pack(">I", 8 + len(body)) + b"meta" + body

def write_mov(src: str, dst: str, asset_id: str) -> None:
    # Stream-copy with metadata stripped and NO faststart, so moov sits after
    # mdat and inserting the meta box cannot invalidate chunk offsets.
    tmp = dst + ".tmp.mov"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", src, "-c", "copy",
                    "-map_metadata", "-1", tmp], check=True)
    data = bytearray(open(tmp, "rb").read()); os.unlink(tmp)
    top = _children(data, 0, len(data))
    moov = next(t for t in top if t[0] == "moov")
    _, m_off, m_size, m_hdr = moov
    meta = build_meta_box(asset_id)
    # drop an existing moov-level meta box if present
    for typ, off, size, hdr in _children(data, m_off + m_hdr, m_off + m_size):
        if typ == "meta":
            del data[off:off + size]
            m_size -= size
            break
    insert_at = m_off + m_size
    mdat_starts = [off for typ, off, size, hdr in top if typ == "mdat"]
    data[insert_at:insert_at] = meta
    struct.pack_into(">I", data, m_off, m_size + len(meta))
    if mdat_starts and insert_at <= min(mdat_starts):
        _shift_chunk_offsets(data, m_off, len(meta))
    open(dst, "wb").write(bytes(data))

def _shift_chunk_offsets(data, moov_off, delta):
    _, m_size, m_hdr = _box(data, moov_off)[0], _box(data, moov_off)[1], _box(data, moov_off)[2]
    def walk(start, end):
        for typ, off, size, hdr in _children(data, start, end):
            if typ in ("trak", "mdia", "minf", "stbl"):
                walk(off + hdr, off + size)
            elif typ in ("stco", "co64"):
                cnt = struct.unpack(">I", data[off + hdr + 4:off + hdr + 8])[0]
                p = off + hdr + 8
                for i in range(cnt):
                    if typ == "stco":
                        v = struct.unpack(">I", data[p + 4 * i:p + 4 * i + 4])[0]
                        struct.pack_into(">I", data, p + 4 * i, v + delta)
                    else:
                        v = struct.unpack(">Q", data[p + 8 * i:p + 8 * i + 8])[0]
                        struct.pack_into(">Q", data, p + 8 * i, v + delta)
    walk(moov_off + m_hdr, moov_off + m_size)

def read_mov_ids(path: str):
    data = open(path, "rb").read()
    top = _children(data, 0, len(data))
    moov = next((t for t in top if t[0] == "moov"), None)
    if not moov:
        return {}
    _, m_off, m_size, m_hdr = moov
    meta = next((t for t in _children(data, m_off + m_hdr, m_off + m_size) if t[0] == "meta"), None)
    if not meta:
        return {}
    _, t_off, t_size, t_hdr = meta
    kids = _children(data, t_off + t_hdr, t_off + t_size)
    keys, ilst = [], None
    for typ, off, size, hdr in kids:
        if typ == "keys":
            cnt = struct.unpack(">I", data[off + hdr + 4:off + hdr + 8])[0]
            p = off + hdr + 8
            for _ in range(cnt):
                ksz = struct.unpack(">I", data[p:p + 4])[0]
                keys.append(data[p + 8:p + ksz].decode("utf-8", "replace"))
                p += ksz
        elif typ == "ilst":
            ilst = (off, size, hdr)
    result = {}
    if ilst:
        off, size, hdr = ilst
        for typ, ioff, isize, ihdr in _children(data, off + hdr, off + size):
            # the item's box 'type' field is the 1-based key index
            idx = struct.unpack(">I", data[ioff + 4:ioff + 8])[0]
            dpos = ioff + ihdr
            dsize = struct.unpack(">I", data[dpos:dpos + 4])[0]
            dtype = struct.unpack(">I", data[dpos + 8:dpos + 12])[0]
            value = data[dpos + 16:dpos + dsize]
            if 1 <= idx <= len(keys):
                result[keys[idx - 1]] = value.decode("utf-8", "replace") if dtype == 1 else value.hex()
    return result

# ---------------------------------------------------------------- package
PLIST = """<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
    <dict>
        <key>PFVideoComplementMetadataVersionKey</key>
        <string>1</string>
    </dict>
</plist>
"""

def cmd_make(args):
    asset_id = (args.asset_id or str(uuid.uuid4())).upper()
    os.makedirs(args.outdir, exist_ok=True)
    name = args.name or os.path.splitext(os.path.basename(args.image))[0]
    jpg_out = os.path.join(args.outdir, name + ".jpg")
    mov_out = os.path.join(args.outdir, name + ".mov")
    write_jpg(args.image, jpg_out, asset_id)
    write_mov(args.video, mov_out, asset_id)
    ok = cmd_check(jpg_out, mov_out, quiet=True)
    print(f"asset_id={asset_id}")
    print(f"jpg={jpg_out}")
    print(f"mov={mov_out}")
    print(f"check={'OK' if ok else 'FAILED'}")
    if args.pvt:
        pvt = os.path.join(args.outdir, name + ".pvt")
        os.makedirs(pvt, exist_ok=True)
        shutil.copy(jpg_out, pvt); shutil.copy(mov_out, pvt)
        open(os.path.join(pvt, "metadata.plist"), "w").write(PLIST)
        print(f"pvt={pvt}")
    return 0 if ok else 1

def cmd_check(jpg, mov, quiet=False):
    jid = read_jpg_id(jpg)
    mids = read_mov_ids(mov)
    mid = mids.get("com.apple.quicktime.content.identifier")
    ok = bool(jid) and jid == mid
    if not quiet:
        print(f"jpg id : {jid}")
        print(f"mov id : {mid}")
        print(f"mov keys: {mids}")
        print("PAIR OK" if ok else "NOT A PAIR")
    return ok

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    mk = sub.add_parser("make")
    mk.add_argument("--image", required=True); mk.add_argument("--video", required=True)
    mk.add_argument("--outdir", required=True); mk.add_argument("--name")
    mk.add_argument("--asset-id"); mk.add_argument("--pvt", action="store_true")
    ck = sub.add_parser("check"); ck.add_argument("jpg"); ck.add_argument("mov")
    args = ap.parse_args()
    if args.cmd == "make":
        return cmd_make(args)
    return 0 if cmd_check(args.jpg, args.mov) else 1

if __name__ == "__main__":
    sys.exit(main())
