import requests, os, zipfile, io, json

# Check HF images zip sizes
repo = "hieupth/nightowls_384"
for part in ["images_part001.zip", "images_part002.zip", "images_part003.zip", "annotations.zip"]:
    url = f"https://huggingface.co/datasets/{repo}/resolve/main/{part}"
    try:
        resp = requests.head(url, timeout=15, allow_redirects=True)
        cl = resp.headers.get("content-length", "?")
        gb = int(cl) / 1e9 if cl and cl != "?" else 0
        print(f"{part}: HTTP {resp.status_code}, {cl} bytes ({gb:.2f} GB)")
    except Exception as e:
        print(f"{part}: Error - {e}")

# Try to download annotations.zip (small, 2.8 MB)
ann_url = f"https://huggingface.co/datasets/{repo}/resolve/main/annotations.zip"
print(f"\nDownloading annotations.zip...")
resp = requests.get(ann_url, timeout=30)
if resp.status_code == 200:
    out_path = "D:/temp/nightowls_hf_annotations.zip"
    with open(out_path, "wb") as f:
        f.write(resp.content)
    print(f"  Saved: {out_path} ({len(resp.content):,} bytes)")
    
    # Extract and check
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        names = z.namelist()
        print(f"  Contents: {names}")
        for name in names:
            if name.endswith(".json"):
                with z.open(name) as jf:
                    data = json.load(jf)
                    if isinstance(data, list):
                        print(f"    {name}: {len(data)} entries")
                    elif isinstance(data, dict):
                        print(f"    {name}: keys={list(data.keys())[:5]}")
else:
    print(f"  Failed: HTTP {resp.status_code}")
