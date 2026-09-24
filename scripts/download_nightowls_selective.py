"""
Try to selectively download NightOwls validation images.
The zip is 57.5 GB so we can't download it all.
We'll try to stream and extract only the images we need.
"""
import json, os, zipfile, requests, io, time

ann_path = "D:/SIH   border cctv/dataset/surveillance/night_real/nightowls_validation.json"
with open(ann_path) as f:
    data = json.load(f)

images = data.get("images", [])
annotations = data.get("annotations", [])

# Group images by timestamp proximity to find sequences
# Images with consecutive timestamps belong to the same video sequence
images_sorted = sorted(images, key=lambda x: x.get("timestamp", 0))

sequences = []
current_seq = [images_sorted[0]]
for i in range(1, len(images_sorted)):
    dt = images_sorted[i]["timestamp"] - images_sorted[i-1]["timestamp"]
    if dt < 1000000:  # Within ~1 second = same sequence
        current_seq.append(images_sorted[i])
    else:
        if len(current_seq) >= 10:  # Only keep sequences with 10+ frames
            sequences.append(current_seq)
        current_seq = [images_sorted[i]]
if len(current_seq) >= 10:
    sequences.append(current_seq)

print(f"Found {len(sequences)} sequences with 10+ frames")
print(f"Top 5 sequences by length:")
for i, seq in enumerate(sorted(sequences, key=len, reverse=True)[:5]):
    print(f"  Seq {i}: {len(seq)} frames, timestamps {seq[0]['timestamp']}-{seq[-1]['timestamp']}")

# Pick 3 best sequences: different lengths for variety
best_seqs = sorted(sequences, key=len, reverse=True)[:3]
target_files = set()
for seq in best_seqs:
    for img in seq:
        target_files.add(img["file_name"])

print(f"\nTarget files to download: {len(target_files)}")

# Try streaming download from OX VGG
url = "http://thor.robots.ox.ac.uk/~vgg/data/nightowls/python/nightowls_validation.zip"
print(f"\nAttempting streaming extraction from: {url}")
print("This may take a while for a 57.5 GB zip...")

out_dir = "D:/SIH   border cctv/dataset/surveillance/night_real/nightowls_frames"
os.makedirs(out_dir, exist_ok=True)

downloaded = 0
try:
    # Stream the zip
    response = requests.get(url, stream=True, timeout=30)
    response.raise_for_status()
    
    # Process the zip in streaming mode
    # We need to read the central directory at the end, but we can try
    # to read file-by-file from the stream
    z = zipfile.ZipFile(io.BytesIO(response.content))
    # This won't work for 57.5 GB - we need a different approach
    
except Exception as e:
    print(f"Direct streaming failed: {e}")
    print("\nTrying alternative: download individual files via HTTP range requests...")

# Alternative: Check if individual files are accessible
print("\nTesting individual file access:")
test_file = list(target_files)[:3]
for fname in test_file:
    individual_url = f"http://thor.robots.ox.ac.uk/~vgg/data/nightowls/python/nightowls_validation/{fname}"
    try:
        resp = requests.head(individual_url, timeout=10)
        print(f"  {fname}: HTTP {resp.status_code}")
    except Exception as e:
        print(f"  {fname}: Error - {e}")
