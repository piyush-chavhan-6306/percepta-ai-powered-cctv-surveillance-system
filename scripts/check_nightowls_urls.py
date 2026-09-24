import json, os, requests

ann_path = "D:/SIH   border cctv/dataset/surveillance/night_real/nightowls_validation.json"
with open(ann_path) as f:
    data = json.load(f)

images = data.get("images", [])
sample_file = images[0]["file_name"]
print(f"Sample file: {sample_file}")

# Try various URL patterns
url_patterns = [
    f"https://afteroffice.clapacloud.org/data/nightowls/nightowls_validation/{sample_file}",
    f"http://www.terraced.ai/data/nightowls/nightowls_validation/{sample_file}",
    f"https://afteroffice.clapacloud.org/data/nightowls/{sample_file}",
    f"http://www.terraced.ai/data/nightowls/{sample_file}",
    f"https://afteroffice.clapacloud.org/nightowls/validation/{sample_file}",
]

for url in url_patterns:
    try:
        resp = requests.head(url, timeout=10, allow_redirects=True)
        print(f"  {resp.status_code} - {url[:80]}...")
        if resp.status_code == 200:
            ct = resp.headers.get("content-type", "")
            cl = resp.headers.get("content-length", "?")
            print(f"    Content-Type: {ct}, Length: {cl}")
    except Exception as e:
        print(f"  ERROR - {url[:80]}...: {e}")
