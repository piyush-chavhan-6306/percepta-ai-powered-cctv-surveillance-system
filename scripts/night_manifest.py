import os, json, hashlib

out_dir = "D:/SIH   border cctv/dataset/surveillance/night_real"
mp4_path = os.path.join(out_dir, "nirped_val_sequence.mp4")

with open(mp4_path, "rb") as f:
    md5 = hashlib.md5(f.read()).hexdigest()

file_size = os.path.getsize(mp4_path)

manifest = {
    "dataset": "NIRPed-mini",
    "source_url": "https://github.com/XiaobiaoDai/NIRPed",
    "source_branch": "master",
    "description": "Genuine nighttime Near-Infrared (NIR) pedestrian detection images from driving scenario",
    "modality": "NIGHT_IR",
    "night_format": "Color NIR images captured with 850nm narrow-band filter at night",
    "note": "Real nighttime imagery, NOT synthetic or daytime-to-nighttime conversion",
    "sequences": [
        {
            "name": "nirped_val_sequence.mp4",
            "description": "Nighttime driving scenario with pedestrians, 1280x720, 160 frames",
            "source_resolution": "1280x720",
            "generated_fps": 10,
            "actual_frames": 160,
            "duration_s": 16.0,
            "file_size_bytes": file_size,
            "md5": md5,
            "classes_present": ["pedestrian"],
            "modality": "NIGHT_IR",
            "night_format": "Color NIR 850nm narrow-band filter",
            "daytime_confirmed": "night",
            "annotations": {
                "total_annotations": 596,
                "annotation_file": "val_mini.json",
                "has_tracking_id": True,
                "has_bbox": True,
                "has_distance": True,
                "has_occlusion": True
            },
            "original_image_count": 160,
            "source_images": "data/miniNIRPed/images&pickles/val/*.png"
        }
    ]
}

manifest_path = os.path.join(out_dir, "manifest.json")
with open(manifest_path, "w") as f:
    json.dump(manifest, f, indent=2)
print(f"Manifest saved: {manifest_path}")

# List all files in night_real
for f in os.listdir(out_dir):
    sz = os.path.getsize(os.path.join(out_dir, f))
    print(f"  {f} ({sz:,} bytes)")
