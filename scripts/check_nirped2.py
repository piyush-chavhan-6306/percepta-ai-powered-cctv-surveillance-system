import requests

# Check master branch tree
resp = requests.get('https://api.github.com/repos/XiaobiaoDai/NIRPed/git/trees/master?recursive=1', timeout=15)
if resp.status_code == 200:
    tree = resp.json()
    mini = [t for t in tree.get('tree', []) if 'miniNIRPed' in t.get('path', '')]
    print(f"miniNIRPed files on master: {len(mini)}")
    for t in mini[:30]:
        lfs = " (LFS)" if t.get("lfs_size") else ""
        print(f"  {t['path']} ({t.get('size', '?')} bytes, type={t['type']}{lfs})")
    
    # Also check if there's a JointDetector directory at root
    joint = [t for t in tree.get('tree', []) if t.get('path', '').startswith('data/mini')]
    print(f"\ndata/mini* files: {len(joint)}")
    for t in joint[:20]:
        print(f"  {t['path']} ({t.get('size', '?')} bytes)")
else:
    print(f"HTTP {resp.status_code}: {resp.text[:200]}")

# Try the GitHub contents API for the root
resp2 = requests.get('https://api.github.com/repos/XiaobiaoDai/NIRPed/contents/', timeout=10)
if resp2.status_code == 200:
    items = resp2.json()
    print(f"\nRoot directory contents:")
    for item in items[:20]:
        print(f"  {item['name']} ({item.get('size', 0)} bytes, type={item['type']})")
else:
    print(f"Root contents: HTTP {resp2.status_code}")
