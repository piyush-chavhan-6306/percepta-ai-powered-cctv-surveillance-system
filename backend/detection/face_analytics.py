"""
Border Intelligence Modular Face Analytics Prototype.
Aligned with SIH Problem Statement SIH26187.
Provides lightweight optical face detection on personnel targets.
CRITICAL CONSTRAINT: Explicitly distinguishes Face Detection from Biometric Recognition.
Does NOT hallucinate or fabricate identities.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class FaceDetectionResult:
    """Structured result from face detection analysis."""
    face_detected: bool
    confidence: float
    face_bounding_box: List[float]  # [x1, y1, x2, y2]
    identity_claim: str = "UNIDENTIFIED (Detection Only — Non-Biometric)"
    timestamp: datetime = None
    camera_id: str = "CAM-01"
    track_id: Optional[str] = None
    evidence_snapshot_uri: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "face_detected": self.face_detected,
            "confidence": round(self.confidence, 3),
            "face_bounding_box": self.face_bounding_box,
            "identity_claim": self.identity_claim,
            "timestamp": (self.timestamp or datetime.now(timezone.utc)).isoformat(),
            "camera_id": self.camera_id,
            "track_id": self.track_id,
            "evidence_snapshot_uri": self.evidence_snapshot_uri,
        }


class FaceAnalyticsProcessor:
    """
    Lightweight Face Detection Analytics.
    Detects upper-body facial regions on tracked persons using OpenCV Haar Cascade or gradient contours.
    Strictly reports presence/absence of face without inventing biometric identities.
    """

    def __init__(self, confidence_threshold: float = 0.50) -> None:
        self.confidence_threshold = confidence_threshold
        self.face_cascade = None
        if hasattr(cv2, "CascadeClassifier") and hasattr(cv2, "data") and hasattr(cv2.data, "haarcascades"):
            try:
                cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
                self.face_cascade = cv2.CascadeClassifier(cascade_path)
            except Exception as e:
                logger.warning(f"Could not load face cascade: {e}")

    def detect_face_in_person(
        self,
        frame: np.ndarray,
        person_box: List[float],
        camera_id: str = "CAM-01",
        track_id: Optional[str] = None,
    ) -> Optional[FaceDetectionResult]:
        """
        Scan the upper 35% of a detected person bounding box for facial geometry.
        """
        if frame is None or len(person_box) < 4:
            return None

        h_img, w_img = frame.shape[:2]
        x1, y1, x2, y2 = map(int, person_box[:4])
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w_img, x2), min(h_img, y2)

        pw = x2 - x1
        ph = y2 - y1
        if pw < 20 or ph < 30:
            return None

        # Face is in top 35% of person box
        head_bottom = y1 + int(ph * 0.35)
        head_crop = frame[y1:head_bottom, x1:x2]
        if head_crop.size == 0:
            return None

        gray = cv2.cvtColor(head_crop, cv2.COLOR_BGR2GRAY)

        if self.face_cascade is not None and not self.face_cascade.empty():
            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=3,
                minSize=(15, 15),
            )
            if len(faces) > 0:
                fx, fy, fw, fh = faces[0]
                global_face_box = [
                    float(x1 + fx),
                    float(y1 + fy),
                    float(x1 + fx + fw),
                    float(y1 + fy + fh),
                ]
                return FaceDetectionResult(
                    face_detected=True,
                    confidence=0.82,
                    face_bounding_box=global_face_box,
                    identity_claim="UNIDENTIFIED (Detection Only — Non-Biometric)",
                    timestamp=datetime.now(timezone.utc),
                    camera_id=camera_id,
                    track_id=track_id,
                )

        # A person box is not proof of a visible face. Returning an invented
        # head region mislabeled as face evidence is misleading in an incident
        # dossier, so callers only receive a crop after a real detector match.
        return None


global_face_processor = FaceAnalyticsProcessor()


def get_face_processor() -> FaceAnalyticsProcessor:
    return global_face_processor
