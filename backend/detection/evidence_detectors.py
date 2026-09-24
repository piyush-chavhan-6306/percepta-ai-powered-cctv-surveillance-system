"""
Evidence Detection Module: real face detection and license-plate (ANPR) detection/OCR.

Replaces the previous heuristic crops (top-35% of a person box for "face",
bottom region of a vehicle box for "plate") with actual ONNX models:

  - Face detection:  OpenCV YuNet (models/face/face_detection_yunet_2023mar.onnx),
    a compact single-shot face detector with five-point landmarks. Runs on the
    CPU via OpenCV DNN. Detection ONLY — PERCEPTA performs no face recognition
    and derives no identity from these boxes.

  - Plate detection: YOLOv8n single-class plate detector
    (models/anpr/plate_yolov8n.onnx) via ONNX Runtime, run per tracked vehicle
    on a padded vehicle crop.

  - Plate OCR:       PP-OCRv3 English recognition head
    (models/anpr/en_PP-OCRv3_rec_infer.onnx) with CTC decoding against the
    PaddleOCR en_dict charset. Character-level confidences are averaged for
    the reading score. No dictionary constraints are applied: if the read is
    weak the plate is explicitly marked uncertain rather than "corrected".

Both pipelines are optional at runtime: when a model file is missing the
respective detector reports available=False and callers fall back to the
previous behavior instead of failing the perception loop.

Privacy policy (see docs): live operator view may be masked via
privacy_masking; evidence written here is the authorized security copy.
Face evidence is captured from the ORIGINAL frame — never from the masked
render — so masking the live view does not destroy the forensic record.
"""
from __future__ import annotations

import logging
import os
import re
import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

def _get_models_dir() -> Path:
    """Resolve models directory from centralized config, with fallback."""
    try:
        from backend.config import get_settings
        return Path(get_settings().MODELS_DIR)
    except Exception:
        return Path("models")

MODELS_DIR = _get_models_dir()
FACE_MODEL_PATH = MODELS_DIR / "face" / "face_detection_yunet_2023mar.onnx"
PLATE_MODEL_PATH = MODELS_DIR / "anpr" / "plate_yolov8n.onnx"
OCR_MODEL_PATH = MODELS_DIR / "anpr" / "en_PP-OCRv3_rec_infer.onnx"
OCR_DICT_PATH = MODELS_DIR / "anpr" / "en_dict.txt"
WEAPON_MODEL_PATH = MODELS_DIR / "weapon" / "gun.pt"

# Indian license plate shape: SS NN SS NNNN (e.g. MH 12 AB 1234).
INDIAN_PLATE_PATTERN = re.compile(r"^[A-Z]{2}\s?\d{1,2}\s?[A-Z]{1,3}\s?\d{1,4}$")


# --------------------------------------------------------------------------- #
#  Face detection (YuNet via OpenCV DNN)                                       #
# --------------------------------------------------------------------------- #
class FaceDetector:
    """YuNet-based face detector producing real face boxes for evidence."""

    def __init__(
        self,
        model_path: Path = FACE_MODEL_PATH,
        score_threshold: float = 0.3,
        nms_threshold: float = 0.3,
        top_k: int = 5000,
        input_size: int = 320,
    ) -> None:
        self.model_path = Path(model_path)
        self.score_threshold = score_threshold
        self.nms_threshold = nms_threshold
        self.top_k = top_k
        self.input_size = input_size
        self._detector: Optional["cv2.FaceDetectorYN"] = None
        self._lock = threading.Lock()

    @property
    def available(self) -> bool:
        return self.model_path.exists()

    def _ensure_loaded(self) -> bool:
        if self._detector is not None:
            return True
        if not self.available:
            return False
        try:
            self._detector = cv2.FaceDetectorYN.create(
                str(self.model_path),
                "",
                (self.input_size, self.input_size),
                self.score_threshold,
                self.nms_threshold,
                self.top_k,
            )
            logger.info(f"FaceDetector (YuNet) loaded from {self.model_path}")
            return True
        except Exception as err:
            logger.warning(f"YuNet face detector failed to load: {err}")
            return False

    def detect(self, image: np.ndarray) -> List[Dict]:
        """
        Detect faces in a BGR image.

        Returns a list of dicts: bbox [x1,y1,x2,y2], confidence, landmarks.
        Empty list when the detector is unavailable or nothing is found.

        Surveillance faces are often 10px at native resolution — below YuNet's
        practical floor. When a native pass finds nothing, one 2x upscaled pass
        is attempted (coordinates mapped back), which is what recovers the small
        faces on the VIRAT demo clip. Only alert-time evidence capture calls
        this, so the extra pass is acceptable there.
        """
        if image is None or image.size == 0:
            return []
        if not self._ensure_loaded():
            return []

        faces = self._detect_raw(image)
        if faces:
            return faces

        h, w = image.shape[:2]
        if max(h, w) <= 2560:  # skip upscale on already-huge frames
            up = cv2.resize(image, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
            up_faces = self._detect_raw(up)
            if up_faces:
                for f in up_faces:
                    f["bbox"] = [v / 2.0 for v in f["bbox"]]
                    f["landmarks"] = [[x / 2.0, y / 2.0] for x, y in f["landmarks"]]
                return up_faces
        return []

    def _detect_raw(self, image: np.ndarray) -> List[Dict]:
        """Single YuNet pass at the given resolution."""
        h, w = image.shape[:2]
        with self._lock:
            try:
                self._detector.setInputSize((w, h))
                ok, faces = self._detector.detect(image)
            except Exception as err:
                logger.warning(f"YuNet detect failed: {err}")
                return []
        if not ok or faces is None or len(faces) == 0:
            return []

        out: List[Dict] = []
        for f in faces:
            # YuNet rows are [x, y, w, h, lx1, ly1..lx5, ly5, score] (15 values):
            # corners must be derived as x+w / y+h, NOT read as x2/y2.
            fx, fy, fw, fh = float(f[0]), float(f[1]), float(f[2]), float(f[3])
            x2, y2 = fx + fw, fy + fh
            out.append({
                "bbox": [max(0.0, fx), max(0.0, fy), min(float(w), x2), min(float(h), y2)],
                "confidence": round(float(f[14]), 4),
                "landmarks": [[float(f[4 + 2 * i]), float(f[5 + 2 * i])] for i in range(5)],
            })
        out.sort(key=lambda d: -d["confidence"])
        return out

    def best_face_in_box(
        self,
        image: np.ndarray,
        person_box: Optional[List[float]] = None,
        min_face_px: int = 20,
    ) -> Optional[Dict]:
        """
        Return the highest-confidence face whose centre falls inside
        `person_box` (when given), subject to a minimum pixel size.

        For surveillance footage where faces are small, we detect on the
        person crop region (top 50% of person box) rather than the full
        frame — this is both faster and more accurate for small faces.
        Coordinates are mapped back to the full frame.
        """
        if person_box is not None and len(person_box) >= 4:
            px1, py1, px2, py2 = person_box[:4]
            pw, ph = px2 - px1, py2 - py1
            if pw > 10 and ph > 10:
                # Crop top 50% of person (head/face region) with margin
                margin_x = int(pw * 0.15)
                margin_y = int(ph * 0.05)
                cx1 = max(0, int(px1) - margin_x)
                cy1 = max(0, int(py1) - margin_y)
                cx2 = min(image.shape[1], int(px1 + pw * 0.6) + margin_x)
                cy2 = min(image.shape[0], int(py1 + ph * 0.50) + margin_y)
                crop = image[cy1:cy2, cx1:cx2]
                if crop.size > 0 and crop.shape[0] > 10 and crop.shape[1] > 10:
                    faces = self.detect(crop)
                    if faces:
                        best: Optional[Dict] = None
                        for f in faces:
                            # Map crop coords back to full frame
                            fb = f["bbox"]
                            fw = fb[2] - fb[0]
                            fh = fb[3] - fb[1]
                            if fw < min_face_px or fh < min_face_px:
                                continue
                            # Full-frame coordinates
                            full_cx = cx1 + (fb[0] + fb[2]) / 2.0
                            full_cy = cy1 + (fb[1] + fb[3]) / 2.0
                            if (px1 - 15 <= full_cx <= px2 + 15
                                    and py1 - 15 <= full_cy <= py2 + 15):
                                mapped = {
                                    "bbox": [cx1 + fb[0], cy1 + fb[1],
                                             cx1 + fb[2], cy1 + fb[3]],
                                    "confidence": f["confidence"],
                                    "landmarks": [[cx1 + x, cy1 + y]
                                                   for x, y in f["landmarks"]],
                                }
                                if best is None or mapped["confidence"] > best["confidence"]:
                                    best = mapped
                        if best is not None:
                            return best

        # Fallback: detect on full frame
        faces = self.detect(image)
        if not faces:
            return None

        if person_box is not None and len(person_box) >= 4:
            px1, py1, px2, py2 = person_box[:4]
            best2: Optional[Dict] = None
            for f in faces:
                cx = (f["bbox"][0] + f["bbox"][2]) / 2.0
                cy = (f["bbox"][1] + f["bbox"][3]) / 2.0
                fw = f["bbox"][2] - f["bbox"][0]
                fh = f["bbox"][3] - f["bbox"][1]
                if fw < min_face_px or fh < min_face_px:
                    continue
                if px1 - 15 <= cx <= px2 + 15 and py1 - 15 <= cy <= py2 + 15:
                    if best2 is None or f["confidence"] > best2["confidence"]:
                        best2 = f
            return best2

        for f in faces:
            fw = f["bbox"][2] - f["bbox"][0]
            fh = f["bbox"][3] - f["bbox"][1]
            if fw >= min_face_px and fh >= min_face_px:
                return f
        return None

    @staticmethod
    def crop_face_evidence(
        frame: np.ndarray,
        face_bbox: List[float],
        min_height_px: int = 96,
    ) -> Optional[np.ndarray]:
        """
        Cut a face crop with margin and upscale tiny faces so the evidence file
        is actually viewable. A 10px face stored as 10px is unreadable; stored
        upscaled (with INTER_CUBIC) it at least supports human review. Returns
        None when the box is degenerate.
        """
        if frame is None or frame.size == 0 or not face_bbox or len(face_bbox) < 4:
            return None
        fh_img, fw_img = frame.shape[:2]
        x1, y1, x2, y2 = [float(v) for v in face_bbox[:4]]
        fw, fh = x2 - x1, y2 - y1
        if fw < 4 or fh < 4:
            return None
        # 25% margin each side, clamped to frame
        mx, my = fw * 0.25, fh * 0.25
        cx1, cy1 = max(0, int(x1 - mx)), max(0, int(y1 - my))
        cx2, cy2 = min(fw_img, int(x2 + mx)), min(fh_img, int(y2 + my))
        crop = frame[cy1:cy2, cx1:cx2]
        if crop.size == 0:
            return None
        if crop.shape[0] < min_height_px:
            scale = min_height_px / crop.shape[0]
            crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        return crop.copy()


# --------------------------------------------------------------------------- #
#  License plate detection + OCR (ONNX Runtime)                                #
# --------------------------------------------------------------------------- #
def _load_charset(path: Path) -> List[str]:
    chars = ["<blank>"]
    if path.exists():
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                ch = line.rstrip("\n")
                if ch:
                    chars.append(ch)
    chars.append(" ")  # PaddleOCR models emit a trailing space class
    return chars


class PlateRecognizer:
    """YOLOv8n plate detector + PP-OCRv3 CTC reader, all through ONNX Runtime."""

    DET_INPUT = 640
    OCR_INPUT_H = 48
    OCR_MIN_W = 320

    def __init__(
        self,
        det_path: Path = PLATE_MODEL_PATH,
        ocr_path: Path = OCR_MODEL_PATH,
        dict_path: Path = OCR_DICT_PATH,
        plate_det_conf: float = 0.30,
        ocr_min_confidence: float = 0.55,
    ) -> None:
        self.det_path = Path(det_path)
        self.ocr_path = Path(ocr_path)
        self.dict_path = Path(dict_path)
        self.plate_det_conf = plate_det_conf
        self.ocr_min_confidence = ocr_min_confidence

        self._det_session = None
        self._rec_session = None
        self._charset: List[str] = _load_charset(self.dict_path)
        self._lock = threading.Lock()

    @property
    def available(self) -> bool:
        return self.det_path.exists()

    @property
    def ocr_available(self) -> bool:
        return self.ocr_path.exists() and self.dict_path.exists()

    def _ensure_det(self) -> bool:
        if self._det_session is not None:
            return True
        if not self.available:
            return False
        try:
            import onnxruntime as ort

            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 1
            opts.inter_op_num_threads = 1
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            self._det_session = ort.InferenceSession(
                str(self.det_path), opts, providers=["CPUExecutionProvider"]
            )
            logger.info(f"Plate detector (YOLOv8n) loaded from {self.det_path}")
            return True
        except Exception as err:
            logger.warning(f"Plate detector failed to load: {err}")
            return False

    def _ensure_ocr(self) -> bool:
        if self._rec_session is not None:
            return True
        if not self.ocr_available:
            return False
        try:
            import onnxruntime as ort

            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 1
            opts.inter_op_num_threads = 1
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            self._rec_session = ort.InferenceSession(
                str(self.ocr_path), opts, providers=["CPUExecutionProvider"]
            )
            logger.info(f"Plate OCR (PP-OCRv3) loaded from {self.ocr_path}")
            return True
        except Exception as err:
            logger.warning(f"Plate OCR failed to load: {err}")
            return False

    # ------------------------------ detection ------------------------------ #
    def detect_plates(self, image: np.ndarray) -> List[Dict]:
        """Detect license plates in a full BGR frame. Returns bbox+conf dicts."""
        if image is None or image.size == 0 or not self._ensure_det():
            return []
        h, w = image.shape[:2]
        scale = self.DET_INPUT / max(h, w)
        nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
        blob = np.full((self.DET_INPUT, self.DET_INPUT, 3), 114, np.uint8)
        resized = cv2.resize(image, (nw, nh))
        dy, dx = (self.DET_INPUT - nh) // 2, (self.DET_INPUT - nw) // 2
        blob[dy:dy + nh, dx:dx + nw] = resized

        x = blob[:, :, ::-1].transpose(2, 0, 1).astype(np.float32) / 255.0
        try:
            out = self._det_session.run(None, {"images": np.ascontiguousarray(x[None])})[0]
        except Exception as err:
            logger.warning(f"Plate detection inference failed: {err}")
            return []

        preds = out[0].T  # (8400, 5): cx, cy, w, h, score
        conf = preds[:, 4]
        keep = conf >= self.plate_det_conf
        if not keep.any():
            return []

        results: List[Dict] = []
        boxes = preds[keep, :4]
        scores = conf[keep]
        for b, s in zip(boxes, scores):
            x1 = (b[0] - b[2] / 2 - dx) / scale
            y1 = (b[1] - b[3] / 2 - dy) / scale
            x2 = (b[0] + b[2] / 2 - dx) / scale
            y2 = (b[1] + b[3] / 2 - dy) / scale
            results.append({
                "bbox": [
                    float(np.clip(x1, 0, w)), float(np.clip(y1, 0, h)),
                    float(np.clip(x2, 0, w)), float(np.clip(y2, 0, h)),
                ],
                "confidence": round(float(s), 4),
            })
        results.sort(key=lambda d: -d["confidence"])
        return results

    def detect_in_vehicle(
        self,
        image: np.ndarray,
        vehicle_box: List[float],
        pad_ratio: float = 0.10,
    ) -> Optional[Dict]:
        """
        Detect a plate inside a tracked vehicle's bounding box.

        Runs the detector on the padded vehicle crop and maps the box back to
        full-frame coordinates, so plate evidence stays aligned with the frame.
        """
        if image is None or image.size == 0 or not vehicle_box or len(vehicle_box) < 4:
            return None
        h, w = image.shape[:2]
        vx1, vy1, vx2, vy2 = [float(v) for v in vehicle_box[:4]]
        pw = (vx2 - vx1) * pad_ratio
        ph = (vy2 - vy1) * pad_ratio
        cx1, cy1 = max(0, int(vx1 - pw)), max(0, int(vy1 - ph))
        cx2, cy2 = min(w, int(vx2 + pw)), min(h, int(vy2 + ph))
        if cx2 - cx1 < 24 or cy2 - cy1 < 24:
            return None
        crop = image[cy1:cy2, cx1:cx2]

        plates = self.detect_plates(crop)
        if not plates:
            return None
        best = plates[0]
        bx1, by1, bx2, by2 = best["bbox"]
        best["bbox"] = [bx1 + cx1, by1 + cy1, bx2 + cx1, by2 + cy1]
        return best

    # -------------------------------- OCR ---------------------------------- #
    def _ocr(self, plate_crop: np.ndarray) -> Tuple[str, float]:
        """Run PP-OCRv3 CTC recognition on a plate crop; returns (text, conf)."""
        if not self._ensure_ocr():
            return "", 0.0
        if plate_crop is None or plate_crop.size == 0:
            return "", 0.0

        # PP-OCRv3 rec expects a 3-channel (RGB) image at 48px height even for
        # grayscale-looking plates; single-channel input raises inside ORT.
        if plate_crop.ndim == 2:
            plate_crop = cv2.cvtColor(plate_crop, cv2.COLOR_GRAY2BGR)
        rgb = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2RGB)
        h0, w0 = rgb.shape[:2]
        target_w = max(self.OCR_MIN_W, int(round(w0 * self.OCR_INPUT_H / max(h0, 1))))
        resized = cv2.resize(rgb, (target_w, self.OCR_INPUT_H), interpolation=cv2.INTER_CUBIC)
        x = resized.astype(np.float32) / 255.0
        x = (x - 0.5) / 0.5
        x = x.transpose(2, 0, 1)[None]  # HWC -> CHW -> 1CHW

        try:
            with self._lock:
                logits = self._rec_session.run(None, {"x": np.ascontiguousarray(x)})[0][0]
        except Exception as err:
            logger.warning(f"OCR inference failed: {err}")
            return "", 0.0

        idxs = logits.argmax(1)
        probs = logits.max(1)
        text_chars: List[str] = []
        conf_sum, conf_n = 0.0, 0
        prev = 0
        for t, ix in enumerate(idxs):
            ix = int(ix)
            if ix != prev and ix != 0:
                if ix < len(self._charset):
                    text_chars.append(self._charset[ix])
                    conf_sum += float(probs[t])
                    conf_n += 1
            prev = ix
        text = "".join(text_chars).strip()
        conf = conf_sum / conf_n if conf_n else 0.0
        return text, round(conf, 4)

    @staticmethod
    def _enhance_for_ocr(plate_crop: np.ndarray) -> np.ndarray:
        """CLAHE-on-L + bilateral filter: contrast and noise cleanup for OCR."""
        lab = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2LAB)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4))
        lab[:, :, 0] = clahe.apply(lab[:, :, 0])
        enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        return cv2.bilateralFilter(enhanced, 5, 50, 50)

    def read_plate(
        self,
        frame: np.ndarray,
        plate_bbox: List[float],
    ) -> Dict:
        """
        Crop (with margin), enhance, and OCR a plate bbox in frame coordinates.

        Returns: {text, confidence, is_valid_format, uncertain, crop_bgr}.
        Never invents characters: a weak read is returned as-is and flagged
        uncertain; an empty read yields text="".
        """
        out: Dict = {
            "text": "", "confidence": 0.0, "is_valid_format": False,
            "uncertain": True, "crop_bgr": None,
        }
        if frame is None or frame.size == 0 or not plate_bbox or len(plate_bbox) < 4:
            return out
        h, w = frame.shape[:2]
        px1, py1, px2, py2 = [float(v) for v in plate_bbox[:4]]
        pw, ph = px2 - px1, py2 - py1
        if pw < 8 or ph < 8:
            return out

        # margin crop (10% each side) so character edges are not clipped
        mx, my = pw * 0.10, ph * 0.10
        cx1, cy1 = max(0, int(px1 - mx)), max(0, int(py1 - my))
        cx2, cy2 = min(w, int(px2 + mx)), min(h, int(py2 + my))
        crop = frame[cy1:cy2, cx1:cx2]
        if crop.size == 0:
            return out
        out["crop_bgr"] = crop.copy()

        # upscale small crops so OCR sees characters at a useful size
        if crop.shape[1] < 160:
            f = 160.0 / crop.shape[1]
            crop = cv2.resize(crop, None, fx=f, fy=f, interpolation=cv2.INTER_CUBIC)

        best_text, best_conf = "", 0.0
        for variant in (self._enhance_for_ocr(crop), crop):
            text, conf = self._ocr(variant)
            if conf > best_conf:
                best_text, best_conf = text, conf
            if best_conf >= 0.85:
                break

        out["text"] = best_text
        out["confidence"] = best_conf
        out["is_valid_format"] = bool(INDIAN_PLATE_PATTERN.match(best_text.replace(" ", "")))
        # Confidence gate: below this the read is reported as uncertain rather
        # than silently accepted; no character is ever substituted to pass.
        out["uncertain"] = best_conf < self.ocr_min_confidence or not best_text
        return out


# --------------------------------------------------------------------------- #
#  Weapon detection (YOLO via models/weapon/gun.pt)                            #
# --------------------------------------------------------------------------- #
class WeaponDetector:
    """YOLO-based weapon detector for gun / firearm observation."""

    def __init__(
        self,
        model_path: Path = WEAPON_MODEL_PATH,
        conf_threshold: float = 0.35,
    ) -> None:
        self.model_path = Path(model_path)
        self.conf_threshold = conf_threshold
        self._model = None
        self._lock = threading.Lock()

    @property
    def available(self) -> bool:
        return self.model_path.exists()

    def _ensure_loaded(self) -> bool:
        if self._model is not None:
            return True
        if not self.available:
            return False
        try:
            from ultralytics import YOLO
            self._model = YOLO(str(self.model_path))
            logger.info(f"WeaponDetector loaded from {self.model_path}")
            return True
        except Exception as err:
            logger.warning(f"WeaponDetector failed to load: {err}")
            return False

    def detect(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detect weapons in a BGR image frame or target crop.
        Returns list of dicts: {"bbox": [x1, y1, x2, y2], "confidence": float, "class_name": str}.
        """
        if not self._ensure_loaded() or image is None or image.size == 0:
            return []
        try:
            with self._lock:
                results = self._model(image, conf=self.conf_threshold, verbose=False)
            detections = []
            for r in results:
                boxes = r.boxes
                if boxes is None:
                    continue
                for box in boxes:
                    xyxy = box.xyxy[0].tolist()
                    conf = float(box.conf[0])
                    cls_id = int(box.cls[0])
                    name = r.names.get(cls_id, "gun") if hasattr(r, "names") else "gun"
                    detections.append({
                        "bbox": [round(c, 2) for c in xyxy],
                        "confidence": round(conf, 4),
                        "class_name": name,
                    })
            return detections
        except Exception as err:
            logger.warning(f"Weapon detection failed: {err}")
            return []


# --------------------------------------------------------------------------- #
#  Process-wide singletons (lazy, thread-safe)                                 #
# --------------------------------------------------------------------------- #
_face_detector: Optional[FaceDetector] = None
_plate_recognizer: Optional[PlateRecognizer] = None
_weapon_detector: Optional[WeaponDetector] = None
_singleton_lock = threading.Lock()


def get_face_detector() -> FaceDetector:
    global _face_detector
    with _singleton_lock:
        if _face_detector is None:
            _face_detector = FaceDetector()
        return _face_detector


def get_plate_recognizer() -> PlateRecognizer:
    global _plate_recognizer
    with _singleton_lock:
        if _plate_recognizer is None:
            _plate_recognizer = PlateRecognizer()
        return _plate_recognizer


def get_weapon_detector() -> WeaponDetector:
    global _weapon_detector
    with _singleton_lock:
        if _weapon_detector is None:
            _weapon_detector = WeaponDetector()
        return _weapon_detector

