"""
Batch-update old dataset paths to canonical locations.
Run once, verify, then delete originals.
"""
import re
from pathlib import Path

ROOT = Path(r"D:\SIH   border cctv")

# Files to update (production + scripts + scratch + docs)
# Excludes: venv/, node_modules/, dataset/, the original dataset dirs, .git/
SKIP_DIRS = {
    "venv", "node_modules", ".git", "__pycache__",
    "dataset", "VIRAT", "moth17", "VisDrone2019-MOT-val",
}

# Replacement rules — order matters (longer/more specific first)
REPLACEMENTS = [
    # Absolute Windows paths (scripts that hardcode D:/SIH... or D:\SIH...)
    (r'"D:/SIH   border cctv/dataset/surveillance/', '"D:/SIH   border cctv/dataset/surveillance/'),
    (r'"D:\SIH   border cctv\dataset\surveillance\', '"D:\\SIH   border cctv\\dataset\\surveillance\\'),
    (r'"D:/SIH   border cctv/dataset/surveillance\', '"D:/SIH   border cctv/dataset/surveillance\\'),
    # Relative paths with forward slashes (most common in scripts)
    (r'"dataset/surveillance/', '"dataset/surveillance/'),
    (r"'dataset/surveillance/", "'dataset/surveillance/"),
    (r'f"dataset/surveillance/', 'f"dataset/surveillance/'),
    (r"dataset/surveillance/CCTV 01", "dataset/surveillance/CCTV 01"),
    # Backslash variants (raw strings in some scripts)
    (r'r"dataset\surveillance\\', r'r"dataset\surveillance\\'),
    (r"r'dataset\surveillance\\", r"r'dataset\surveillance\\"),
    # MOT17 / moth17
    (r'"dataset/perimeter/', '"dataset/perimeter/'),
    (r'"dataset\perimeter\', '"dataset\\perimeter\\'),
    (r'dataset/perimeter / "MOT17"', 'dataset/perimeter / "MOT17"'),
    (r'dataset/perimeter" / "MOT17"', 'dataset/perimeter" / "MOT17"'),
    (r'"dataset/perimeter/MOT17', '"dataset/perimeter/MOT17'),
    # VisDrone
    (r'"dataset/drone/VisDrone2019-MOT-val/', '"dataset/drone/VisDrone2019-MOT-val/'),
    (r'dataset/drone/VisDrone2019-MOT-val" /', 'dataset/drone/dataset/drone/VisDrone2019-MOT-val" /'),
    # datasets/virat (lowercase, old placeholder)
    (r'"dataset/surveillance', '"dataset/surveillance'),
    (r'dataset/surveillance/', 'dataset/surveillance/'),
]

# Also handle escaped backslashes in JSON/strings
JSON_REPLACEMENTS = [
    ('"dataset\\surveillance\\\\', '"dataset\\\\surveillance\\\\'),
    ('"dataset\perimeter\\\', '"dataset\\\\perimeter\\\\'),
    ('"dataset\\drone\\VisDrone2019-MOT-val\\\\', '"dataset\\\\drone\\\\VisDrone2019-MOT-val\\\\'),
]

def find_python_files(root: Path) -> list[Path]:
    """Find all Python, JSON, YAML, MD files to update."""
    files = []
    for ext in ("*.py", "*.json", "*.yaml", "*.yml", "*.md", "*.txt", "*.env"):
        for f in root.rglob(ext):
            # Skip directories we don't want to touch
            parts = f.relative_to(root).parts
            if any(d in SKIP_DIRS for d in parts):
                continue
            files.append(f)
    return files

def update_file(path: Path, dry_run: bool = False) -> list[str]:
    """Apply all replacements to a file. Returns list of changes made."""
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
    
    original = content
    changes = []
    
    for old, new in REPLACEMENTS:
        if old in content:
            content = content.replace(old, new)
            changes.append(f"  {old!r} -> {new!r}")
    
    for old, new in JSON_REPLACEMENTS:
        if old in content:
            content = content.replace(old, new)
            changes.append(f"  {old!r} -> {new!r}")
    
    if changes and not dry_run:
        path.write_text(content, encoding="utf-8")
    
    return changes

def main():
    files = find_python_files(ROOT)
    print(f"Scanning {len(files)} files...")
    
    updated = 0
    for f in sorted(files):
        changes = update_file(f, dry_run=False)
        if changes:
            rel = f.relative_to(ROOT)
            print(f"\n{rel}:")
            for c in changes:
                print(c)
            updated += 1
    
    print(f"\nUpdated {updated} files")

if __name__ == "__main__":
    main()
