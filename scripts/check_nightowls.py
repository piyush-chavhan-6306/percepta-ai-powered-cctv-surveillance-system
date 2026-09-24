import json, os, requests, time

ann_path = "D:/SIH   border cctv/dataset/surveillance/night_real/nightowls_validation.json"
with open(ann_path) as f:
    data = json.load(f)

print(f"NightOwls validation dataset:")
print(f"  Images: {len(data.get('images', []))}")
print(f"  Annotations: {len(data.get('annotations', []))}")
print(f"  Categories: {len(data.get('categories', []))}")

# Check categories
cats = data.get("categories", [])
for c in cats[:10]:
    print(f"    Category {c.get('id')}: {c.get('name')}")

# Check first few images
images = data.get("images", [])
print(f"\nFirst 5 images:")
for img in images[:5]:
    print(f"  {img}")

# Check if there's a video_file or file_name pattern
print(f"\nImage keys: {list(images[0].keys()) if images else 'none'}")

# Look for video grouping
video_ids = set()
for img in images:
    vid = img.get("video_id") or img.get("seq_id") or img.get("sequence_id")
    if vid:
        video_ids.add(vid)
print(f"\nUnique video/sequence IDs: {len(video_ids)}")
if video_ids:
    print(f"  Sample IDs: {list(video_ids)[:10]}")

# Check if images have URLs
has_url = any("url" in img or "file_name" in img for img in images[:5])
print(f"\nImages have file_name or url: {has_url}")
