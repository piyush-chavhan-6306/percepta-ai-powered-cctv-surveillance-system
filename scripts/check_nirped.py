import requests

resp = requests.get('https://api.github.com/repos/XiaobiaoDai/NIRPed/branches', timeout=10)
if resp.status_code == 200:
    branches = resp.json()
    for b in branches:
        print(f"Branch: {b['name']}")
else:
    print(f"HTTP {resp.status_code}")

resp2 = requests.get('https://api.github.com/repos/XiaobiaoDai/NIRPed/git/trees/JointDetector?recursive=1', timeout=15)
if resp2.status_code == 200:
    tree = resp2.json()
    mini = [t for t in tree.get('tree', []) if 'miniNIRPed' in t.get('path', '')]
    print(f"\nminiNIRPed files found: {len(mini)}")
    for t in mini[:20]:
        print(f"  {t['path']} ({t.get('size', '?')} bytes, type={t['type']})")
else:
    print(f"Tree API: HTTP {resp2.status_code}")
