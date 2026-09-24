"""Verify Phase 2 paths and backend startup."""
from backend.config import get_settings
from pathlib import Path

s = get_settings()
print(f"MODELS_DIR: {s.MODELS_DIR}")
print(f"DATASETS_DIR: {s.DATASETS_DIR}")
print(f"RUNTIME_DIR: {s.RUNTIME_DIR}")

models = Path(s.MODELS_DIR)
checks = {
    "yolov8n.onnx": models / "yolov8n.onnx",
    "yunet.onnx": models / "face_detection_yunet_2023mar.onnx",
    "plate.onnx": models / "anpr" / "plate_yolov8n.onnx",
    "reid.onnx": models / "reid" / "osnet_x0_25_msmt17.onnx",
    "weapon.gun.pt": models / "weapon" / "gun.pt",
}
for name, path in checks.items():
    print(f"  {name}: {'OK' if path.exists() else 'MISSING'}")

dataset = Path(s.DATASETS_DIR)
ds_checks = {
    "surveillance": dataset / "surveillance",
    "perimeter": dataset / "perimeter",
    "drone": dataset / "drone",
}
for name, path in ds_checks.items():
    count = len(list(path.rglob("*"))) if path.exists() else 0
    print(f"  dataset/{name}: {count} files")

runtime = Path(s.RUNTIME_DIR)
for sub in ("evidence", "clips", "snapshots", "exports", "logs", "cache"):
    print(f"  runtime/{sub}: {'OK' if (runtime / sub).exists() else 'MISSING'}")

# Verify imports work
from backend.database import Base, engine, SessionLocal
from backend.database.schema import CameraModel, DetectionModel
from backend.types import CameraID, SessionID
from backend.contracts import DetectionResult, BBox
print("\nAll imports OK")

# Verify app starts
from backend.main import app
routes = [r.path for r in app.routes]
print(f"Routes loaded: {len(routes)}")
