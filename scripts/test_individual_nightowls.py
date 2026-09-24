import requests, json

ann_path = "D:/SIH   border cctv/dataset/surveillance/night_real/nightowls_validation.json"
with open(ann_path) as f:
    data = json.load(f)

images = data.get("images", [])
test_files = [img["file_name"] for img in images[:5]]

base_url = "http://thor.robots.ox.ac.uk/~vgg/data/nightowls/python/nightowls_validation"
for fname in test_files:
    url = f"{base_url}/{fname}"
    try:
        resp = requests.head(url, timeout=10)
        cl = resp.headers.get("content-length", "?")
        print(f"{fname}: HTTP {resp.status_code}, size={cl}")
    except Exception as e:
        print(f"{fname}: Error - {e}")
