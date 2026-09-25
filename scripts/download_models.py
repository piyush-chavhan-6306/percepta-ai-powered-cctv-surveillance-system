"""
PERCEPTA — Model Manifest Downloader & Bundle Verifier.
Pre-downloads, verifies, and stages all surveillance weights into ./models/ for offline deployment.
"""
import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from backend.core.model_manager import MODELS_MANIFEST, verify_models


def main():
    print("=== PERCEPTA Surveillance Model Weight Verification & Downloader ===")
    print("Checking canonical model manifest...")

    result = verify_models(base_dir=project_root, auto_download=True, check_hashes=True)

    print("\n--- Manifest Verification Results ---")
    for m in result["models"]:
        size_mb = m["size_bytes"] / (1024 * 1024)
        print(f"[{m['status']}] {m['name']} ({size_mb:.2f} MB) -> {m['path']}")

    if result["all_required_ok"]:
        print("\n[SUCCESS] All required model weights are provisioned and verified for offline execution.")
    else:
        print(f"\n[ALERT] Missing required models: {', '.join(result['missing_required'])}")
        sys.exit(1)


if __name__ == "__main__":
    main()
