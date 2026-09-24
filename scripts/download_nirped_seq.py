"""Download miniNIRPed night vision validation images from GitHub."""
import requests
import os
import json
import time

REPO = "XiaobiaoDai/NIRPed"
BRANCH = "master"
OUT_DIR = "D:/temp/nirped"
os.makedirs(OUT_DIR, exist_ok=True)

# First, get the list of all miniNIRPed files
print("Listing miniNIRPed files...")
resp = requests.get(
    f"https://api.github.com/repos/{REPO}/git/trees/{BRANCH}?recursive=1",
    timeout=30
)
if resp.status_code != 200:
    print(f"Failed to list: HTTP {resp.status_code}")
    exit(1)

tree = resp.json()
all_files = tree.get("tree", [])

# Get annotation files
ann_files = [t for t in all_files if t["path"].endswith(".json") and "miniNIRPed" in t["path"]]
# Get image files (PNG) from validation
val_images = [t for t in all_files if t["path"].startswith("data/miniNIRPed/images&pickles/val/") and t["path"].endswith(".png")]

print(f"Annotation files: {len(ann_files)}")
for f in ann_files:
    print(f"  {f['path']} ({f.get('size', 0):,} bytes)")

print(f"Validation images: {len(val_images)}")
if val_images:
    total_size = sum(f.get("size", 0) for f in val_images)
    print(f"  Total size: {total_size/1e6:.1f} MB")

# Download annotations first (small files)
for f in ann_files:
    url = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/{f['path']}"
    fname = os.path.basename(f["path"])
    out_path = os.path.join(OUT_DIR, fname)
    print(f"Downloading {fname}...")
    resp = requests.get(url, timeout=30)
    if resp.status_code == 200:
        with open(out_path, "wb") as fh:
            fh.write(resp.content)
        print(f"  Saved: {out_path} ({len(resp.content):,} bytes)")
    else:
        print(f"  Failed: HTTP {resp.status_code}")

# Download validation images (up to 200 for a reasonable sequence)
# Sort by filename to get chronological order
val_images.sort(key=lambda x: x["path"])
max_images = 200
selected = val_images[:max_images]

print(f"\nDownloading {len(selected)} validation images...")
downloaded = 0
failed = 0
for i, f in enumerate(selected):
    url = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/{f['path']}"
    fname = os.path.basename(f["path"])
    out_path = os.path.join(OUT_DIR, "val_images", fname)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        downloaded += 1
        continue

    resp = requests.get(url, timeout=30)
    if resp.status_code == 200:
        with open(out_path, "wb") as fh:
            fh.write(resp.content)
        downloaded += 1
    else:
        failed += 1

    if (i + 1) % 20 == 0:
        print(f"  Progress: {i+1}/{len(selected)} (downloaded={downloaded}, failed={failed})")
        time.sleep(0.5)  # Be nice to GitHub

print(f"\nDone: {downloaded} downloaded, {failed} failed")
print(f"Images in: {os.path.join(OUT_DIR, 'val_images')}")
