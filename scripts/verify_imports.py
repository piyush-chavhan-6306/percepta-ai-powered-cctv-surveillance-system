"""Verify all imports and app startup after dataset path migration."""
import sys
sys.path.insert(0, r"D:\SIH   border cctv")

from backend.config import get_settings
from backend.database import Base, init_db, get_db_session, close_db
from backend.database.schema import Camera, Detection, Event, Incident, Alert
from backend.types import CameraID, SessionID
from backend.contracts import DetectionResult, BBox
from backend.detection.evidence_detectors import FaceDetector, PlateRecognizer
from backend.detection.onnx_detector import OnnxDetector
from backend.tracking.reid_manager import REID_MODEL_INFO
print("All imports OK")
print(f"ReID weights path: {REID_MODEL_INFO['weights']}")

from backend.main import app
routes = [r.path for r in app.routes]
print(f"App routes: {len(routes)}")
print("Startup verification PASSED")
