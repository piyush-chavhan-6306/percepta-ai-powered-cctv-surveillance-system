import requests

# Check if OX VGG server is accessible
urls_to_test = [
    "http://thor.robots.ox.ac.uk/~vgg/data/nightowls/python/nightowls_validation.zip",
    "http://thor.robots.ox.ac.uk/~vgg/data/nightowls/matlab/videos_set01.zip",
]

for url in urls_to_test:
    print(f"Testing: {url}")
    try:
        resp = requests.head(url, timeout=15, allow_redirects=True)
        print(f"  Status: {resp.status_code}")
        ct = resp.headers.get("content-type", "?")
        cl = resp.headers.get("content-length", "?")
        print(f"  Content-Type: {ct}, Length: {cl}")
        if cl:
            gb = int(cl) / 1e9
            print(f"  Size: {gb:.1f} GB")
    except Exception as e:
        print(f"  Error: {e}")
    print()

# Also test Hugging Face LFS
print("Testing Hugging Face LFS:")
hf_url = "https://huggingface.co/datasets/hieupth/nightowls_384/resolve/main/annotations.zip"
try:
    resp = requests.head(hf_url, timeout=15, allow_redirects=True)
    print(f"  Status: {resp.status_code}")
    cl = resp.headers.get("content-length", "?")
    print(f"  Length: {cl}")
except Exception as e:
    print(f"  Error: {e}")
