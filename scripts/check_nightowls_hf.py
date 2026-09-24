import requests, os, json

# Check Hugging Face NightOwls dataset
repo = "hieupth/nightowls_384"
api_url = f"https://huggingface.co/api/datasets/{repo}"
resp = requests.get(api_url, timeout=15)
if resp.status_code == 200:
    info = resp.json()
    print(f"Dataset: {info.get('id')}")
    print(f"Description: {info.get('description', 'N/A')[:200]}")
    
    # Check sibling files
    siblings = info.get("siblings", [])
    print(f"\nFiles: {len(siblings)}")
    for s in siblings:
        print(f"  {s.get('rfilename')} ({s.get('size', '?')} bytes)")
else:
    print(f"HTTP {resp.status_code}")

# Also try to check the original nightowls-dataset.org download page
print("\n--- Checking nightowls-dataset.org ---")
try:
    resp2 = requests.get("https://www.nightowls-dataset.org/download/", timeout=10)
    print(f"HTTP {resp2.status_code}")
    if resp2.status_code == 200:
        # Find download links
        import re
        links = re.findall(r'href="([^"]*)"', resp2.text)
        download_links = [l for l in links if "download" in l.lower() or ".zip" in l.lower() or ".tar" in l.lower()]
        for l in download_links[:10]:
            print(f"  Link: {l}")
except Exception as e:
    print(f"Error: {e}")
