import os

dirs = {
    "D:/temp": "D:\\temp",
    "D:/temp/ptb_tir_extracted": "D:\\temp\\ptb_tir_extracted",
    "D:/temp/nirped": "D:\\temp\\nirped",
    "D:/SIH   border cctv/dataset/surveillance/thermal_real": "dataset\\surveillance\\thermal_real",
    "D:/SIH   border cctv/dataset/surveillance/night_real": "dataset\\surveillance\\night_real",
}

for path, label in dirs.items():
    print(f"=== {label} ===")
    if not os.path.exists(path):
        print("  NOT FOUND")
        print()
        continue
    entries = os.listdir(path)
    for e in sorted(entries):
        full = os.path.join(path, e)
        if os.path.isfile(full):
            sz = os.path.getsize(full)
            print(f"  {e} ({sz:,} bytes, {sz/1e6:.1f} MB)")
        elif os.path.isdir(full):
            count = len(os.listdir(full))
            print(f"  {e}/ ({count} items)")
    print()

# Check D:\temp top-level for archives
print("=== D:\\temp archives ===")
for f in os.listdir("D:/temp"):
    full = os.path.join("D:/temp", f)
    if os.path.isfile(full):
        sz = os.path.getsize(full)
        print(f"  {f} ({sz:,} bytes, {sz/1e6:.1f} MB)")

# Check ptb_tir subdirectories
print("\n=== PTB-TIR extracted sequences ===")
seq_base = "D:/temp/ptb_tir_extracted/tirsequences"
if os.path.exists(seq_base):
    seqs = sorted(os.listdir(seq_base))
    print(f"  Total sequences: {len(seqs)}")
    for s in seqs:
        img_dir = os.path.join(seq_base, s, "img")
        if os.path.isdir(img_dir):
            imgs = [f for f in os.listdir(img_dir) if f.endswith(".jpg")]
            print(f"    {s}: {len(imgs)} frames")
