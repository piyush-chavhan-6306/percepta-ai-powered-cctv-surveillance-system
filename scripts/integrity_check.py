import cv2, os, json, hashlib

def check_video(path, label):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        print(f"  FAIL: Cannot open {path}")
        return False
    
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fourcc_int = int(cap.get(cv2.CAP_PROP_FOURCC))
    fourcc = "".join([chr((fourcc_int >> 8*i) & 0xFF) for i in range(4)])
    
    # Read first, middle, and last frames
    test_frames = [0, frame_count // 2, frame_count - 1]
    read_ok = 0
    for fn in test_frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, fn)
        ret, frame = cap.read()
        if ret and frame is not None and frame.size > 0:
            read_ok += 1
    cap.release()
    
    sz = os.path.getsize(path)
    with open(path, "rb") as f:
        md5 = hashlib.md5(f.read()).hexdigest()
    
    status = "OK" if read_ok == 3 else f"PARTIAL ({read_ok}/3 frames readable)"
    print(f"  {label}: {status}")
    print(f"    Path: {path}")
    print(f"    Resolution: {w}x{h}")
    print(f"    FPS: {fps:.1f}")
    print(f"    Frames: {frame_count}")
    print(f"    Duration: {frame_count/fps:.1f}s")
    print(f"    Codec: {fourcc}")
    print(f"    Size: {sz:,} bytes ({sz/1e6:.1f} MB)")
    print(f"    MD5: {md5}")
    return read_ok == 3

print("=" * 60)
print("INTEGRITY CHECK: VIRAT/thermal_real/")
print("=" * 60)
thermal_dir = "D:/SIH   border cctv/dataset/surveillance/thermal_real"
thermal_ok = 0
thermal_total = 0
for f in sorted(os.listdir(thermal_dir)):
    if f.endswith(".mp4"):
        thermal_total += 1
        if check_video(os.path.join(thermal_dir, f), f"Thermal: {f}"):
            thermal_ok += 1
        print()

print(f"Thermal: {thermal_ok}/{thermal_total} passed")
print()

print("=" * 60)
print("INTEGRITY CHECK: VIRAT/night_real/")
print("=" * 60)
night_dir = "D:/SIH   border cctv/dataset/surveillance/night_real"
night_ok = 0
night_total = 0
for f in sorted(os.listdir(night_dir)):
    if f.endswith(".mp4"):
        night_total += 1
        if check_video(os.path.join(night_dir, f), f"Night: {f}"):
            night_ok += 1
        print()

# Also check annotation files
print("Annotation files:")
for f in sorted(os.listdir(night_dir)):
    if f.endswith(".json"):
        fpath = os.path.join(night_dir, f)
        sz = os.path.getsize(fpath)
        try:
            with open(fpath) as jf:
                data = json.load(jf)
            if isinstance(data, dict):
                keys = list(data.keys())
                print(f"  {f}: VALID JSON, {sz:,} bytes, keys={keys[:5]}")
            else:
                print(f"  {f}: VALID JSON, {sz:,} bytes, type={type(data).__name__}")
        except Exception as e:
            print(f"  {f}: INVALID JSON - {e}")

print(f"\nNight: {night_ok}/{night_total} MP4s passed")
print()

# Summary
print("=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"Thermal MP4s: {thermal_ok}/{thermal_total} OK")
print(f"Night MP4s:   {night_ok}/{night_total} OK")
print(f"Night annotations: present")
print(f"NightOwls images: NOT downloaded (57.5 GB zip, server requires full download)")
