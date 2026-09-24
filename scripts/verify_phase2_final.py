"""Verify all model and dataset paths resolve correctly after Phase 2 restructure."""
import sys
sys.path.insert(0, r"D:\SIH   border cctv")

from pathlib import Path
from backend.config import get_settings

s = get_settings()
models = Path(s.MODELS_DIR)
dataset = Path(s.DATASETS_DIR)
runtime = Path(s.RUNTIME_DIR)

print("=== MODEL PATH VERIFICATION ===")
checks = {
    "detection/yolov8n.onnx": models / "detection" / "yolov8n.onnx",
    "detection/yolov8n.pt": models / "detection" / "yolov8n.pt",
    "face/face_detection_yunet_2023mar.onnx": models / "face" / "face_detection_yunet_2023mar.onnx",
    "anpr/plate_yolov8n.onnx": models / "anpr" / "plate_yolov8n.onnx",
    "anpr/en_PP-OCRv3_rec_infer.onnx": models / "anpr" / "en_PP-OCRv3_rec_infer.onnx",
    "anpr/en_dict.txt": models / "anpr" / "en_dict.txt",
    "reid/osnet_x0_25_msmt17.onnx": models / "reid" / "osnet_x0_25_msmt17.onnx",
    "weapon/gun.pt": models / "weapon" / "gun.pt",
}
all_ok = True
for name, path in checks.items():
    exists = path.exists()
    if not exists:
        all_ok = False
    print(f"  {name}: {'OK' if exists else 'MISSING'}")

print("\n=== DATASET PATH VERIFICATION ===")
ds_checks = {
    "surveillance": dataset / "surveillance",
    "perimeter": dataset / "perimeter",
    "drone": dataset / "drone",
}
for name, path in ds_checks.items():
    count = len(list(path.rglob("*"))) if path.exists() else 0
    print(f"  {name}: {count} items")

print("\n=== RUNTIME DIR VERIFICATION ===")
for sub in ("evidence", "clips", "snapshots", "exports", "logs", "cache"):
    print(f"  {sub}: {'OK' if (runtime / sub).exists() else 'MISSING'}")

print("\n=== IMPORT VERIFICATION ===")
from backend.detection.evidence_detectors import FACE_MODEL_PATH, PLATE_MODEL_PATH, WEAPON_MODEL_PATH
from backend.detection.onnx_detector import OnnxDetector
from backend.tracking.reid_manager import REID_MODEL_INFO
from backend.detection.model_loader import ModelLoader

print(f"  FACE_MODEL_PATH: {FACE_MODEL_PATH} exists={FACE_MODEL_PATH.exists()}")
print(f"  PLATE_MODEL_PATH: {PLATE_MODEL_PATH} exists={PLATE_MODEL_PATH.exists()}")
print(f"  WEAPON_MODEL_PATH: {WEAPON_MODEL_PATH} exists={WEAPON_MODEL_PATH.exists()}")
print(f"  ReID weights: {REID_MODEL_INFO['weights']}")

print(f"\n{'ALL CHECKS PASSED' if all_ok else 'SOME CHECKS FAILED'}")
