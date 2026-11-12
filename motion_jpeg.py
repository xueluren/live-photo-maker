#!/usr/bin/env python3
"""Build a single-file Motion Photo JPEG: the still JPEG with the video
embedded after it, described by Google GCamera XMP (MotionPhoto=1 +
Container directory). One .jpg file; supporting viewers play the video,
other viewers just show the photo. Apple Photos does NOT animate this
format (Apple Live Photos are a JPG+MOV pair instead)."""
import struct, sys

XMP_HEADER = b"http://ns.adobe.com/xap/1.0/\x00"

def build_xmp(video_len: int) -> bytes:
    xmp = f'''<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="live-photo-maker">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about="" xmlns:GCamera="http://ns.google.com/photos/1.0/camera/" xmlns:Container="http://ns.google.com/photos/1.0/container/" xmlns:Item="http://ns.google.com/photos/1.0/container/item/" GCamera:MotionPhoto="1" GCamera:MotionPhotoPresentationTimestampUs="0">
   <Container:Directory>
    <rdf:Seq>
     <rdf:li rdf:parseType="Resource">
      <Item:Mime>image/jpeg</Item:Mime>
      <Item:Semantic>Primary</Item:Semantic>
      <Item:Length>0</Item:Length>
      <Item:Padding>0</Item:Padding>
     </rdf:li>
     <rdf:li rdf:parseType="Resource">
      <Item:Mime>video/mp4</Item:Mime>
      <Item:Semantic>MotionPhoto</Item:Semantic>
      <Item:Length>{video_len}</Item:Length>
     </rdf:li>
    </rdf:Seq>
   </Container:Directory>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>'''.encode("utf-8")
    payload = XMP_HEADER + xmp
    seg = b"\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload
    return seg

def make(jpg_path, mp4_path, out_path):
    jpg = open(jpg_path, "rb").read()
    mp4 = open(mp4_path, "rb").read()
    assert jpg[:2] == b"\xff\xd8", "not a JPEG"
    assert mp4[4:8] == b"ftyp", "not an MP4"
    xmp_seg = build_xmp(len(mp4))
    out = jpg[:2] + xmp_seg + jpg[2:] + mp4
    open(out_path, "wb").write(out)
    return len(out)

if __name__ == "__main__":
    n = make(sys.argv[1], sys.argv[2], sys.argv[3])
    print(f"wrote {sys.argv[3]} ({n} bytes)")
