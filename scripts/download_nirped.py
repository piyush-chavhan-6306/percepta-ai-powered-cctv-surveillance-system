"""Download miniNIRPed night vision dataset from GitHub."""
import requests
import os
import json

REPO = "XiaobiaoDai/NIRPed"
REF = "JointDetector"
OUT_DIR = "D:/temp/nirped"

os.makedirs(OUT_DIR, exist_ok=True)

files_to_check = [
    ("val_ann", "data/miniNIRPed/val/annotations.json"),
    ("val_images", "data/miniNIRPed/val/images.zip"),
    ("test_info", "data/miniNIRPed/test/test_info.json"),
    ("test_images", "data/miniNIRPed/test/images.zip"),
]

for label, fpath in files_to_check:
    api_url = f"https://api.github.com/repos/{REPO}/contents/{fpath}?ref={REF}"
    print(f"Checking {fpath}...")
    resp = requests.get(api_url, timeout=15)
    if resp.status_code == 200:
        data = resp.json()
        size = data.get("size", 0)
        print(f"  Size: {size:,} bytes ({size/1e6:.1f} MB)")
        if "download_url" in data:
            dl_url = data["download_url"]
            print(f"  Direct download URL available: {dl_url[:80]}...")
            # Try downloading
            out_path = os.path.join(OUT_DIR, f"{label}.bin")
            print(f"  Downloading to {out_path}...")
            dl_resp = requests.get(dl_url, timeout=60, stream=True)
            if dl_resp.status_code == 200:
                total = int(dl_resp.headers.get("content-length", 0))
                downloaded = 0
                with open(out_path, "wb") as f:
                    for chunk in dl_resp.iter_content(chunk_size=1024*1024):
                        f.write(chunk)
                        downloaded += len(chunk)
                print(f"  Downloaded: {downloaded:,} bytes")
            else:
                print(f"  Download failed: HTTP {dl_resp.status_code}")
        else:
            print(f"  No direct download URL")
            # Check if content is available
            if "content" in data:
                content = data.get("content", "")
                encoding = data.get("encoding", "")
                print(f"  Encoding: {encoding}, content length: {len(content)}")
    else:
        print(f"  HTTP {resp.status_code}")
    print()
