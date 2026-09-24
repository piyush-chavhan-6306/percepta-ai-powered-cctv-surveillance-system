"""
Border Intelligence Camera Tamper Detector.
Detects camera sabotage, physical occlusion, blinding, and tampering events
such as spray painting, lens capping, laser/spotlight blinding, and deliberate defocusing.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import List, Optional, Tuple
import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class TamperDetectionResult:
    """Structured result of camera integrity and tamper analysis."""
    is_tampered: bool
    reasons: List[str]
    blur_score: float
    mean_intensity: float
    std_intensity: float
    camera_id: str = "CAM-01"
    timestamp: Optional[datetime] = None


class CameraTamperDetector:
    """
    Lightweight Camera Tamper & Lens Sabotage Detector.
    Evaluates individual video frames for optical anomalies indicating physical sabotage:
    1. Black frame: Lens covered with opaque cap or black spray paint (mean < 15.0).
    2. White frame: Camera blinded by tactical laser or direct spotlight (mean > 240.0).
    3. Defocus / Blur: Lens covered in grease, spray, or defocused (Laplacian var < 15.0).
    4. Uniform obstruction: Solid uniform cloth or object obstructing view (std < 8.0).
    Includes consecutive-frame debouncing to eliminate transient lighting false alarms.
    """

    def __init__(
        self,
        black_threshold: float = 15.0,
        white_threshold: float = 240.0,
        blur_threshold: float = 15.0,
        uniformity_threshold: float = 8.0,
        consecutive_frames_trigger: int = 3,
    ) -> None:
        self.black_threshold = black_threshold
        self.white_threshold = white_threshold
        self.blur_threshold = blur_threshold
        self.uniformity_threshold = uniformity_threshold
        self.consecutive_frames_trigger = consecutive_frames_trigger

        self._consecutive_tamper_count = 0
        self._last_tamper_state = False

    def reset(self) -> None:
        """Reset tamper state counter."""
        self._consecutive_tamper_count = 0
        self._last_tamper_state = False

    def evaluate_frame(
        self,
        frame: np.ndarray,
        camera_id: str = "CAM-01",
    ) -> TamperDetectionResult:
        """
        Analyze frame for optical tampering signatures in < 1 ms.
        Downsamples to 160x120 for instant CPU processing without eating inference budget.
        """
        if frame is None or frame.size == 0:
            return TamperDetectionResult(
                is_tampered=True,
                reasons=["EMPTY_FRAME_SIGNAL_LOSS"],
                blur_score=0.0,
                mean_intensity=0.0,
                std_intensity=0.0,
                camera_id=camera_id,
                timestamp=datetime.now(timezone.utc),
            )

        # Fast downsample for microscopic CPU overhead
        h, w = frame.shape[:2]
        small = cv2.resize(frame, (160, 120), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY) if len(small.shape) == 3 else small

        mean_val = float(np.mean(gray))
        std_val = float(np.std(gray))
        blur_val = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        reasons: List[str] = []

        if mean_val < self.black_threshold and std_val < self.uniformity_threshold:
            reasons.append("LENS_OCCLUSION_BLACK")
        elif mean_val > self.white_threshold and std_val < self.uniformity_threshold:
            reasons.append("CAMERA_BLINDED_WHITE")
        elif std_val < self.uniformity_threshold and (mean_val < 30 or mean_val > 220):
            reasons.append("UNIFORM_OBSTRUCTION")
        elif blur_val < self.blur_threshold and std_val > 15.0:
            reasons.append("SEVERE_OPTICAL_DEFOCUS")

        frame_tampered = len(reasons) > 0

        if frame_tampered:
            self._consecutive_tamper_count += 1
        else:
            self._consecutive_tamper_count = max(0, self._consecutive_tamper_count - 1)

        confirmed_tamper = self._consecutive_tamper_count >= self.consecutive_frames_trigger
        self._last_tamper_state = confirmed_tamper

        if confirmed_tamper and self._consecutive_tamper_count == self.consecutive_frames_trigger:
            logger.warning(
                f"[TAMPER ALERT] Camera '{camera_id}' sabotage detected! Reasons={reasons}, "
                f"mean={mean_val:.1f}, std={std_val:.1f}, blur={blur_val:.1f}"
            )

        return TamperDetectionResult(
            is_tampered=confirmed_tamper,
            reasons=reasons,
            blur_score=round(blur_val, 2),
            mean_intensity=round(mean_val, 2),
            std_intensity=round(std_val, 2),
            camera_id=camera_id,
            timestamp=datetime.now(timezone.utc),
        )


_tamper_detectors: dict[str, CameraTamperDetector] = {}


def get_tamper_detector(camera_id: str) -> CameraTamperDetector:
    """Get or create per-camera tamper detector."""
    if camera_id not in _tamper_detectors:
        _tamper_detectors[camera_id] = CameraTamperDetector()
    return _tamper_detectors[camera_id]
