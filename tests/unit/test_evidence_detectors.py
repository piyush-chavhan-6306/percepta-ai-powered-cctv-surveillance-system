"""
Unit tests for the real evidence detectors (face/plate/OCR) and multi-frame
plate aggregation.

Model-backed tests are skipped automatically when the ONNX weights are not
present locally, so the suite stays green on machines without the model cache.
"""
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

from backend.detection.evidence_detectors import (
    INDIAN_PLATE_PATTERN,
    FaceDetector,
    PlateRecognizer,
    get_plate_recognizer,
)
from backend.detection.plate_aggregator import PlateEvidenceCollector

try:
    from backend.config import get_settings
    _MODELS = Path(get_settings().MODELS_DIR)
except Exception:
    _MODELS = Path("models")

MODELS_OK = (_MODELS / "anpr" / "plate_yolov8n.onnx").exists()
FACE_OK = (_MODELS / "face" / "face_detection_yunet_2023mar.onnx").exists()
OCR_OK = (_MODELS / "anpr" / "en_PP-OCRv3_rec_infer.onnx").exists()


def _scene_with_plate(text="MH12AB1234", x=300, y=380, w=160, h=40):
    """Synthetic scene: car body + white plate with black text."""
    img = np.full((720, 1280, 3), 70, np.uint8)
    import cv2
    cv2.rectangle(img, (150, 260), (560, 430), (40, 40, 180), -1)
    cv2.rectangle(img, (x, y), (x + w, y + h), (245, 245, 245), -1)
    import cv2 as _cv
    fs = h / 42.0
    _cv.putText(img, text, (x + 4, y + int(h * 0.78)), _cv.FONT_HERSHEY_SIMPLEX,
                fs, (15, 15, 15), max(2, int(round(fs * 3.2))), _cv.LINE_AA)
    return img


# ----------------------------------------------------------------- aggregator
def test_aggregator_consensus_prefers_repeated_high_confidence():
    col = PlateEvidenceCollector()
    ts = datetime.now(timezone.utc)
    col.add_observation("cam:1", "MH12AB1234", 0.61, 101, ts)
    col.add_observation("cam:1", "MH12AB1234", 0.82, 102, ts)
    col.add_observation("cam:1", "MH12AB1284", 0.54, 103, ts)
    best = col.get_best("cam:1")
    assert best is not None
    # The consistent high-confidence reading outranks the one-off low one.
    assert best.text == "MH12AB1234"
    assert best.confidence == 0.82
    assert best.hits == 2
    assert not best.uncertain


def test_aggregator_marks_lone_weak_reading_uncertain():
    col = PlateEvidenceCollector()
    col.add_observation("cam:2", "MH12AB1234", 0.40, 5, datetime.now(timezone.utc))
    best = col.get_best("cam:2")
    assert best is not None
    assert best.uncertain is True


def test_aggregator_never_invents_a_reading():
    col = PlateEvidenceCollector()
    assert col.get_best("missing-track") is None


def test_aggregator_bounds_memory_per_track():
    col = PlateEvidenceCollector()
    ts = datetime.now(timezone.utc)
    for i in range(50):
        col.add_observation("cam:3", f"MH12AB{i:04d}", 0.9, i, ts)
    assert len(col._tracks["cam:3"]) <= 12


def test_aggregator_evicts_oldest_track():
    col = PlateEvidenceCollector(max_tracks=2)
    ts = datetime.now(timezone.utc)
    for t in ("a", "b", "c"):
        col.add_observation(t, "MH12AB1234", 0.9, 1, ts)
    assert "a" not in col._tracks


# -------------------------------------------------------------------- format
def test_indian_plate_pattern_accepts_and_rejects():
    assert INDIAN_PLATE_PATTERN.match("MH12AB1234")
    assert INDIAN_PLATE_PATTERN.match("DL1CAB1234")
    assert not INDIAN_PLATE_PATTERN.match("HELLO")
    assert not INDIAN_PLATE_PATTERN.match("123456")


# ------------------------------------------------------- detector smoke tests
@pytest.mark.skipif(not MODELS_OK, reason="plate detector weights not staged")
def test_plate_detector_finds_synthetic_plate():
    pr = get_plate_recognizer()
    img = _scene_with_plate()
    plates = pr.detect_plates(img)
    assert plates, "plate detector found nothing on a clear synthetic plate"
    assert plates[0]["confidence"] > 0.4


@pytest.mark.skipif(not MODELS_OK or not OCR_OK, reason="OCR weights not staged")
def test_ocr_reads_synthetic_plate_and_gates_confidence():
    pr = get_plate_recognizer()
    img = _scene_with_plate()
    plates = pr.detect_plates(img)
    reading = pr.read_plate(img, plates[0]["bbox"])
    assert reading["text"].upper().replace(" ", "") == "MH12AB1234"
    assert reading["confidence"] > 0.7
    assert reading["is_valid_format"]
    assert not reading["uncertain"]


@pytest.mark.skipif(not MODELS_OK, reason="plate detector weights not staged")
def test_detect_in_vehicle_maps_box_to_frame_coords():
    pr = get_plate_recognizer()
    img = _scene_with_plate()
    hit = pr.detect_in_vehicle(img, [150.0, 260.0, 560.0, 460.0])
    assert hit is not None
    x1, y1, x2, y2 = hit["bbox"]
    # plate drawn at (300,380)-(460,420): mapped box must overlap it
    assert x1 < 460 and x2 > 300 and y1 < 420 and y2 > 380


@pytest.mark.skipif(not FACE_OK, reason="YuNet weights not staged")
def test_face_detector_returns_no_face_on_blank_scene():
    fd = FaceDetector()
    blank = np.full((480, 640, 3), 90, np.uint8)
    assert fd.detect(blank) == []
    assert fd.best_face_in_box(blank, [100, 100, 300, 400]) is None


@pytest.mark.skipif(not FACE_OK, reason="YuNet weights not staged")
def test_face_evidence_crop_upscales_small_faces():
    from backend.detection.evidence_detectors import FaceDetector as FD
    frame = np.full((720, 1280, 3), 80, np.uint8)
    crop = FD.crop_face_evidence(frame, [100.0, 100.0, 112.0, 114.0], min_height_px=96)
    # 12px face + margins upscaled to at least min_height_px
    assert crop is not None
    assert crop.shape[0] >= 96


def test_plate_recognizer_graceful_without_models(tmp_path):
    """Detector reports unavailable and returns empty instead of raising."""
    pr = PlateRecognizer(
        det_path=tmp_path / "missing.onnx",
        ocr_path=tmp_path / "missing_rec.onnx",
        dict_path=tmp_path / "missing_dict.txt",
    )
    assert pr.available is False
    assert pr.detect_plates(np.zeros((100, 100, 3), np.uint8)) == []
    assert pr.detect_in_vehicle(np.zeros((200, 200, 3), np.uint8), [10, 10, 90, 90]) is None
    out = pr.read_plate(np.zeros((60, 60, 3), np.uint8), [10, 10, 50, 40])
    assert out["text"] == "" and out["uncertain"]


def test_weapon_detector_availability_and_inference():
    from backend.detection.evidence_detectors import WeaponDetector, get_weapon_detector
    wd = get_weapon_detector()
    assert isinstance(wd, WeaponDetector)
    assert wd.available is True
    blank = np.zeros((320, 320, 3), dtype=np.uint8)
    hits = wd.detect(blank)
    assert isinstance(hits, list)
    assert len(hits) == 0


def test_weapon_detector_graceful_without_model(tmp_path):
    from backend.detection.evidence_detectors import WeaponDetector
    wd = WeaponDetector(model_path=tmp_path / "missing_gun.pt")
    assert wd.available is False
    assert wd.detect(np.zeros((100, 100, 3), dtype=np.uint8)) == []

