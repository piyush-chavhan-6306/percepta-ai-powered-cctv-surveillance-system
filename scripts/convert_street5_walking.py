import os, cv2, json, hashlib, time

base = "D:/temp/ptb_tir_extracted/tirsequences"
output_dir = "D:/SIH   border cctv/dataset/surveillance/thermal_real"

selected = [
    ("street5", "Street patrol scene, VGA 640x471, 140 frames, pedestrians"),
    ("walking", "Walking scene, VGA 640x360, 315 frames, pedestrians"),
]

manifest_path = os.path.join(output_dir, "manifest.json")
with open(manifest_path) as f:
    manifest = json.load(f)

for seq_name, description in selected:
    img_dir = os.path.join(base, seq_name, "img")
    imgs = sorted([f for f in os.listdir(img_dir) if f.endswith(".jpg")])
    first_frame = cv2.imread(os.path.join(img_dir, imgs[0]))
    h, w = first_frame.shape[:2]

    output_path = os.path.join(output_dir, f"ptb_tir_{seq_name}.mp4")
    fps = 30
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(output_path, fourcc, fps, (w, h))

    print(f"Converting {seq_name} ({len(imgs)} frames, {w}x{h})...")
    t0 = time.time()
    for i, fname in enumerate(imgs):
        frame = cv2.imread(os.path.join(img_dir, fname))
        if frame is not None:
            writer.write(frame)
        if (i+1) % 50 == 0:
            print(f"  {i+1}/{len(imgs)}")
    writer.release()
    elapsed = time.time() - t0

    file_size = os.path.getsize(output_path)
    with open(output_path, "rb") as f:
        md5 = hashlib.md5(f.read()).hexdigest()

    cap = cv2.VideoCapture(output_path)
    actual_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()

    seq_info = {
        "name": f"ptb_tir_{seq_name}.mp4",
        "original_sequence_id": seq_name,
        "description": description,
        "source_resolution": f"{w}x{h}",
        "generated_fps": fps,
        "actual_frames_in_mp4": actual_frames,
        "original_frame_count": len(imgs),
        "duration_s": round(len(imgs) / fps, 2),
        "file_size_bytes": file_size,
        "md5": md5,
        "classes_present": ["pedestrian"],
        "modality": "THERMAL_INFRARED",
        "thermal_format": "Grayscale thermal stored as 3-channel BGR JPEG",
        "source_url": "https://sites.google.com/view/ptb-tir/download",
    }
    manifest["sequences"].append(seq_info)
    print(f"  -> {output_path} ({file_size/1e6:.1f} MB, {actual_frames} frames, {elapsed:.1f}s)")

with open(manifest_path, "w") as f:
    json.dump(manifest, f, indent=2)
print(f"\nManifest updated: {manifest_path}")
