"""
Border Intelligence Optical Quality & Lens Tampering Diagnostics Module.
Analyzes CCTV video frames for physical lens occlusion, spray tampering, blinding glare, and optical degradation.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
import cv2
import numpy as np
from pydantic import BaseModel

from backend.ingestion.camera_manager import get_camera_manager


class SignalQualityStatus(str, Enum):
    OPTIMAL = "OPTIMAL"
    OCCLUDED_OR_BLURRED = "OCCLUDED_OR_BLURRED"
    BLINDED_GLARE = "BLINDED_GLARE"
    LOW_LIGHT_DEGRADED = "LOW_LIGHT_DEGRADED"
    STREAM_FROZEN = "STREAM_FROZEN"


class CameraDiagnostics(BaseModel):
    camera_id: str
    status: SignalQualityStatus
    blur_score: float
    brightness_mean: float
    glare_percentage: float
    darkness_percentage: float
    is_tampered_or_degraded: bool
    diagnosis_message: str


def is_night_movement_condition(
    timestamp: Optional[datetime] = None,
    brightness_mean: float = 80.0,
    night_start_hour: int = 22,
    night_end_hour: int = 5,
) -> bool:
    """
    Check if a surveillance event occurs during night hours or severe low-light conditions.
    """
    ts = timestamp or datetime.now(timezone.utc)
    hour = ts.hour
    is_night_hours = (hour >= night_start_hour or hour < night_end_hour)
    is_sensor_dark = brightness_mean < 35.0
    return is_night_hours or is_sensor_dark


def evaluate_optical_quality(
    image: np.ndarray,
    camera_id: str = "CAM-01",
    prev_image: Optional[np.ndarray] = None,
) -> CameraDiagnostics:
    """
    Evaluate optical signal quality, lens tampering, and stream freeze metrics using fast NumPy/OpenCV matrix math.
    Execution time: < 0.2ms per frame.
    """
    if image is None or image.size == 0:
        return CameraDiagnostics(
            camera_id=camera_id,
            status=SignalQualityStatus.OCCLUDED_OR_BLURRED,
            blur_score=0.0,
            brightness_mean=0.0,
            glare_percentage=0.0,
            darkness_percentage=100.0,
            is_tampered_or_degraded=True,
            diagnosis_message="SIGNAL LOST: Frame buffer is empty or zero-dimensioned.",
        )

    # Convert to grayscale if 3-channel
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    # 1. Blur / Lens Occlusion via Laplacian Variance
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    blur_score = float(lap.var())

    # 2. Luminance and Clipping
    mean_val = float(np.mean(gray))
    total_pixels = gray.size
    glare_pixels = int(np.sum(gray >= 245))
    dark_pixels = int(np.sum(gray <= 15))

    glare_pct = round((glare_pixels / total_pixels) * 100.0, 1)
    dark_pct = round((dark_pixels / total_pixels) * 100.0, 1)

    # 3. Stream Freeze Detection (if previous frame provided)
    is_frozen = False
    if prev_image is not None and prev_image.size > 0:
        if prev_image.shape == image.shape:
            diff = cv2.absdiff(image, prev_image)
            if float(np.mean(diff)) < 0.05:
                is_frozen = True

    # 4. Determine Optical Diagnosis
    if is_frozen:
        status = SignalQualityStatus.STREAM_FROZEN
        tampered = True
        msg = f"CAMERA HEALTH WARNING: Stream frozen / video playback stalled on '{camera_id}'."
    elif glare_pct >= 35.0:
        status = SignalQualityStatus.BLINDED_GLARE
        tampered = True
        msg = f"TAMPER/OPTICAL WARNING: High blinding glare / saturation detected ({glare_pct}% overexposed)."
    elif dark_pct >= 75.0 and mean_val < 20.0:
        status = SignalQualityStatus.LOW_LIGHT_DEGRADED
        tampered = True
        msg = f"DEGRADATION WARNING: Severe low-light or sensor blackout ({dark_pct}% underexposed)."
    elif blur_score < 30.0:
        status = SignalQualityStatus.OCCLUDED_OR_BLURRED
        tampered = True
        msg = f"TAMPER/OCCLUSION WARNING: Lens spray, heavy blur, or physical obstruction detected (score: {blur_score:.1f})."
    else:
        status = SignalQualityStatus.OPTIMAL
        tampered = False
        msg = f"NOMINAL: CCTV optical clarity and exposure are optimal (blur: {blur_score:.1f}, brightness: {mean_val:.1f})."

    return CameraDiagnostics(
        camera_id=camera_id,
        status=status,
        blur_score=round(blur_score, 2),
        brightness_mean=round(mean_val, 2),
        glare_percentage=glare_pct,
        darkness_percentage=dark_pct,
        is_tampered_or_degraded=tampered,
        diagnosis_message=msg,
    )


async def diagnose_camera_stream(camera_id: str) -> Optional[CameraDiagnostics]:
    """Fetch the latest frame from a camera and run optical diagnostics."""
    manager = get_camera_manager()
    cam = manager.get_camera(camera_id)
    if not cam:
        return None

    frame_data = await manager.get_latest_frame(camera_id)
    if frame_data is None or frame_data.image is None:
        return CameraDiagnostics(
            camera_id=camera_id,
            status=SignalQualityStatus.OCCLUDED_OR_BLURRED,
            blur_score=0.0,
            brightness_mean=0.0,
            glare_percentage=0.0,
            darkness_percentage=100.0,
            is_tampered_or_degraded=True,
            diagnosis_message=f"Camera '{camera_id}' is offline or not actively yielding frames.",
        )

    return evaluate_optical_quality(frame_data.image, camera_id=camera_id)
