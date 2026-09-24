"""
Border Intelligence ONNX Runtime Detector.
Each camera gets its own ONNX session for true parallel inference
without the shared-model inference lock bottleneck.

ONNX Runtime is thread-safe — each session maintains its own
execution context, so 3 cameras can detect simultaneously at full speed.
"""
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional

import os
import cv2
import numpy as np

logger = logging.getLogger(__name__)

# COCO surveillance target classes
DEFAULT_SURVEILLANCE_CLASSES = {
    0: "person",
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    4: "airplane",
    5: "bus",
    6: "train",
    7: "truck",
    8: "boat",
}


class OnnxDetector:
    """
    Lightweight ONNX Runtime detector — one instance per camera.
    No shared state, no locks needed.
    """

    # COCO class id -> per-class confidence floor.
    # Diagnostics on project footage (scratch/diagnose_pipeline_issues.py) showed:
    #   - motorcycle (3) peaks around 0.27 because two-wheelers are rare in COCO
    #     and at equal confidence lose per-class NMS against the car box around
    #     the rider, so they need a lower floor than the global threshold;
    #   - train (6) false-positives up to ~0.41 on building/roof-like structures
    #     in the aerial clip, far below any real train would score, so it needs
    #     a raised floor. Measured FP max on project clips: 0.409.
    CLASS_CONF_FLOORS: Dict[int, float] = {
        3: 0.10,   # motorcycle
        1: 0.10,   # bicycle (same small-rider profile)
        6: 0.55,   # train — suppress structural false positives
        4: 0.55,   # airplane — same structural-FP profile, drone surrogate
    }

    def __init__(
        self,
        onnx_path: str = "",
        conf_threshold: float = 0.32,
        iou_threshold: float = 0.45,
        imgsz: int = 416,
        target_classes: Optional[Dict[int, str]] = None,
        person_conf_threshold: float = 0.28,
    ) -> None:
        if not onnx_path:
            try:
                from backend.config import get_settings
                settings = get_settings()
                onnx_path = str(Path(settings.MODELS_DIR) / "detection" / "yolov8n.onnx")
            except Exception:
                onnx_path = "models/detection/yolov8n.onnx"
        self.onnx_path = onnx_path
        self.conf_threshold = conf_threshold
        self.person_conf_threshold = person_conf_threshold
        self.iou_threshold = iou_threshold
        self.imgsz = imgsz
        self.target_classes = target_classes or DEFAULT_SURVEILLANCE_CLASSES
        self.target_class_ids = list(self.target_classes.keys())

        self._session = None
        self._input_name = None
        self._is_initialized = False
        self.device = "cpu"
        self.active_provider = "CPUExecutionProvider"
        # Pre-allocated buffers for fast preprocessing
        self._buf_canvas = None
        self._buf_resized = None
        self._buf_float = None
        self._buf_h = 0
        self._buf_w = 0

    def initialize(self) -> None:
        """Load ONNX model and warm up."""
        if self._is_initialized:
            return

        import onnxruntime as ort

        path = Path(self.onnx_path)
        if not path.exists():
            raise FileNotFoundError(f"ONNX model not found: {path}")

        # Optimal execution options for ultra-low latency & zero memory fragmentation
        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        # Intra-op threads: measured on the project dev machine (12 logical
        # cores): yolov8n@416 latency 43.2ms (1 thread) -> 28.6ms (2) -> 17.1ms
        # (4) -> 17.4ms (6) -> 17.8ms (8). Latency plateaus at 4 threads; more
        # threads only add scheduling overhead and steal CPU from decode/render
        # threads. Capped at min(4, cores) and never below 2. Detection output
        # verified bit-identical between 2 and 4 threads on real footage.
        opts.intra_op_num_threads = max(2, min(4, os.cpu_count() or 2))
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        opts.enable_mem_pattern = True
        opts.enable_cpu_mem_arena = True
        opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL

        # Dynamic provider resolution (automatic GPU acceleration with seamless CPU fallback)
        available = ort.get_available_providers()
        providers = []
        if "TensorrtExecutionProvider" in available:
            providers.append("TensorrtExecutionProvider")
        if "CUDAExecutionProvider" in available:
            providers.append("CUDAExecutionProvider")
        providers.append("CPUExecutionProvider")

        self._session = ort.InferenceSession(
            str(path), opts, providers=providers
        )
        self._input_name = self._session.get_inputs()[0].name
        self._is_initialized = True

        active_providers = self._session.get_providers()
        self.active_provider = active_providers[0] if active_providers else "CPUExecutionProvider"
        if "CUDAExecutionProvider" in self.active_provider or "TensorrtExecutionProvider" in self.active_provider:
            self.device = "gpu"
        else:
            self.device = "cpu"

        logger.info(f"ONNX detector initialized: {path.name} (imgsz={self.imgsz}, device={self.device}, provider={self.active_provider})")
        self._warmup()

    def _warmup(self) -> None:
        """Throwaway inferences to prime ONNX kernels."""
        blank = np.zeros((1, 3, self.imgsz, self.imgsz), dtype=np.float32)
        for _ in range(3):
            self._session.run(None, {self._input_name: blank})

    def _preprocess(self, image: np.ndarray) -> np.ndarray:
        """BGR uint8 → NCHW float32 tensor, letterbox-padded.
        Uses pre-allocated buffers to avoid per-frame memory allocation.
        """
        h, w = image.shape[:2]
        if self._buf_canvas is None or self._buf_h != h or self._buf_w != w:
            # First call or resolution changed: pre-allocate buffers
            scale = self.imgsz / max(h, w)
            new_w = int(w * scale)
            new_h = int(h * scale)
            self._new_w, self._new_h = new_w, new_h
            self._buf_h, self._buf_w = h, w
            self._buf_resized = np.empty((new_h, new_w, 3), dtype=np.uint8)
            self._buf_canvas = np.full((self.imgsz, self.imgsz, 3), 114, dtype=np.uint8)
            self._buf_float = np.empty((1, 3, self.imgsz, self.imgsz), dtype=np.float32)
            dy = (self.imgsz - new_h) // 2
            dx = (self.imgsz - new_w) // 2
            self._pad_dy, self._pad_dx = dy, dx
            self._scale = scale
            # Pre-compute source slice for reuse
            self._canvas_region = (slice(dy, dy + new_h), slice(dx, dx + new_w))

        # Resize (reuses pre-allocated buffer)
        cv2.resize(image, (self._new_w, self._new_h), dst=self._buf_resized, interpolation=cv2.INTER_LINEAR)

        # Reset canvas padding color and copy resized region
        self._buf_canvas[:] = 114
        self._buf_canvas[self._canvas_region] = self._buf_resized

        # BGR→RGB + HWC→CHW + normalize in one pass using pre-allocated float buffer
        # Split channels from canvas (B,G,R) and write directly to float buf (R,G,B)
        f = self._buf_float[0]
        f[0] = self._buf_canvas[:, :, 2]  # R
        f[1] = self._buf_canvas[:, :, 1]  # G
        f[2] = self._buf_canvas[:, :, 0]  # B
        f *= (1.0 / 255.0)
        return self._buf_float

    def _postprocess(
        self, output: np.ndarray, orig_h: int, orig_w: int
    ) -> List[Dict]:
        """Parse YOLO output tensor → filtered detections with constant-time C++ NMS."""
        # output shape: (1, 84, N) → transpose to (N, 84)
        preds = output[0].T  # (N, 84)

        # Extract boxes and scores
        boxes_xywh = preds[:, :4]  # cx, cy, w, h
        class_scores = preds[:, 4:]  # 80 class scores

        # Filter to target surveillance classes
        target_scores = class_scores[:, self.target_class_ids]
        max_scores = target_scores.max(axis=1)
        class_indices = target_scores.argmax(axis=1)
        mapped_cls_ids = np.array(self.target_class_ids)[class_indices]

        # Sensitive person floor: catches distant or low-contrast persons (conf >= 0.12)
        # while keeping general surveillance threshold (conf >= 0.15) for vehicles
        person_thresh = getattr(self, "person_conf_threshold", 0.12)
        # Per-class floors: two-wheelers sit below the global threshold (see
        # CLASS_CONF_FLOORS); train/airplane structural false positives need a
        # raised floor instead of silently hiding the class.
        global_floor = min(self.conf_threshold, 1.0)
        floors = np.full(len(self.target_class_ids), global_floor, dtype=np.float32)
        for pos, cid in enumerate(self.target_class_ids):
            if cid == 0:
                floors[pos] = min(person_thresh, self.conf_threshold)
            elif cid in self.CLASS_CONF_FLOORS:
                floors[pos] = self.CLASS_CONF_FLOORS[cid]
        thresholds = floors[class_indices]
        mask = max_scores >= thresholds
        if not mask.any():
            return []

        boxes = boxes_xywh[mask]
        scores = max_scores[mask]
        cls_ids = mapped_cls_ids[mask]

        # Pre-filter top-300 candidates to guarantee constant <0.3ms NMS latency under dense scene load
        if len(scores) > 300:
            top_k = scores.argsort()[-300:]
            boxes = boxes[top_k]
            scores = scores[top_k]
            cls_ids = cls_ids[top_k]

        # Convert xywh → xyxy
        x1 = boxes[:, 0] - boxes[:, 2] / 2
        y1 = boxes[:, 1] - boxes[:, 3] / 2
        x2 = boxes[:, 0] + boxes[:, 2] / 2
        y2 = boxes[:, 1] + boxes[:, 3] / 2

        # Scale back to original image coordinates (unletterbox)
        scale = getattr(self, "_scale", self.imgsz / max(orig_h, orig_w))
        dx = float(getattr(self, "_pad_dx", (self.imgsz - int(orig_w * scale)) // 2))
        dy = float(getattr(self, "_pad_dy", (self.imgsz - int(orig_h * scale)) // 2))
        x1 = np.clip((x1 - dx) / scale, 0, orig_w)
        y1 = np.clip((y1 - dy) / scale, 0, orig_h)
        x2 = np.clip((x2 - dx) / scale, 0, orig_w)
        y2 = np.clip((y2 - dy) / scale, 0, orig_h)

        # High-speed per-class NMS using OpenCV C++ engine
        detections = []
        for cls_id_val in np.unique(cls_ids):
            cls_mask = (cls_ids == cls_id_val)
            sub_x1 = x1[cls_mask]
            sub_y1 = y1[cls_mask]
            sub_x2 = x2[cls_mask]
            sub_y2 = y2[cls_mask]
            sub_scores = scores[cls_mask]

            cv_boxes = [
                [float(sub_x1[i]), float(sub_y1[i]), float(sub_x2[i] - sub_x1[i]), float(sub_y2[i] - sub_y1[i])]
                for i in range(len(sub_x1))
            ]
            cv_scores = [float(s) for s in sub_scores]

            try:
                indices = cv2.dnn.NMSBoxes(cv_boxes, cv_scores, score_threshold=0.0, nms_threshold=self.iou_threshold)
                if len(indices) == 0:
                    continue
                if hasattr(indices, "flatten"):
                    indices = indices.flatten()
                elif isinstance(indices, (tuple, list)):
                    indices = [int(idx[0]) if hasattr(idx, "__len__") else int(idx) for idx in indices]
            except Exception:
                # Fallback to python NMS if cv2.dnn encounters unexpected input
                cls_boxes = np.stack([sub_x1, sub_y1, sub_x2, sub_y2], axis=1)
                indices = self._nms(cls_boxes, sub_scores, self.iou_threshold)

            for idx in indices:
                idx = int(idx)
                bx0, by0, bx1_v, by1_v = sub_x1[idx], sub_y1[idx], sub_x2[idx], sub_y2[idx]
                sc = float(sub_scores[idx])
                detections.append({
                    "class_id": int(cls_id_val),
                    "class_name": self.target_classes.get(int(cls_id_val), "unknown"),
                    "confidence": round(sc, 4),
                    "bbox": [round(float(bx0), 2), round(float(by0), 2),
                             round(float(bx1_v), 2), round(float(by1_v), 2)],
                    "norm": [
                        round(max(0, min(1, float(bx0) / orig_w)), 4),
                        round(max(0, min(1, float(by0) / orig_h)), 4),
                        round(max(0, min(1, float(bx1_v) / orig_w)), 4),
                        round(max(0, min(1, float(by1_v) / orig_h)), 4),
                    ],
                })
        return detections

    @staticmethod
    def _nms(boxes: np.ndarray, scores: np.ndarray, iou_thresh: float) -> List[int]:
        """Fast NMS fallback — returns indices of kept boxes."""
        if len(boxes) == 0:
            return []
        x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
        areas = (x2 - x1) * (y2 - y1)
        order = scores.argsort()[::-1]
        keep = []
        while len(order) > 0:
            i = order[0]
            keep.append(int(i))
            if len(order) == 1:
                break
            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])
            inter = np.maximum(0, xx2 - xx1) * np.maximum(0, yy2 - yy1)
            iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-6)
            inds = np.where(iou <= iou_thresh)[0]
            order = order[inds + 1]
        return keep

    def detect(self, image: np.ndarray) -> List[Dict]:
        """
        Run ONNX inference on a BGR image.
        Returns list of dicts with class_id, class_name, confidence, bbox, norm.
        Thread-safe — each instance has its own ONNX session.
        """
        if not self._is_initialized:
            self.initialize()

        if image is None or not isinstance(image, np.ndarray) or image.size == 0:
            return []

        h, w = image.shape[:2]
        if h == 0 or w == 0:
            return []

        try:
            blob = self._preprocess(image)
            outputs = self._session.run(None, {self._input_name: blob})
            return self._postprocess(outputs[0], h, w)
        except Exception as e:
            logger.error(
                f"[INFERENCE ERROR] ONNX Runtime execution failed on {w}x{h} frame: {e} "
                f"(model={self.onnx_path}, provider={self._session.get_providers() if self._session else 'none'})",
                exc_info=True
            )
            return []

    def release(self) -> None:
        """Release ONNX InferenceSession and clear pre-allocated memory buffers."""
        if self._session is not None:
            try:
                del self._session
            except Exception as e:
                logger.warning(f"Error releasing ONNX session for {self.onnx_path}: {e}")
            self._session = None
        self._input_name = None
        self._is_initialized = False
        self._buf_canvas = None
        self._buf_resized = None
        self._buf_float = None
        logger.info(f"ONNX detector session released for {self.onnx_path}")


# Global registry — one ONNX detector per camera
_onnx_detectors: Dict[str, OnnxDetector] = {}


def get_onnx_detector(camera_id: str) -> OnnxDetector:
    """Get or create a per-camera ONNX detector honoring the camera's inference size."""
    if camera_id not in _onnx_detectors:
        from backend.config import get_settings
        settings = get_settings()
        imgsz = settings.DEFAULT_INFERENCE_SIZE
        # Per-camera inference size: aerial/drone sources need 640 for small
        # objects; fixed CCTV stays at the cheaper size. Unknown camera -> auto.
        try:
            from backend.ingestion.camera_manager import get_camera_manager
            rec = get_camera_manager().get_camera(camera_id)
            if rec is not None:
                size_cfg = (getattr(rec, "inference_size", "auto") or "auto").lower()
                if size_cfg == "auto":
                    imgsz = 640 if "aerial" in (rec.name or "").lower() or "aerial" in (rec.location_label or "").lower() else 416
                else:
                    imgsz = int(size_cfg)
        except Exception:
            pass
        _onnx_detectors[camera_id] = OnnxDetector(
            onnx_path=str(Path(settings.MODELS_DIR) / "detection" / "yolov8n.onnx"),
            conf_threshold=settings.CONFIDENCE_THRESHOLD,
            iou_threshold=settings.IOU_THRESHOLD,
            imgsz=imgsz,
        )
        _onnx_detectors[camera_id].initialize()
    return _onnx_detectors[camera_id]


def release_onnx_detector(camera_id: str) -> bool:
    """Release and remove the per-camera ONNX detector instance to prevent memory leaks."""
    detector = _onnx_detectors.pop(camera_id, None)
    if detector is not None:
        detector.release()
        return True
    return False
