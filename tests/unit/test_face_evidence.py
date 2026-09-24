import numpy as np

from backend.detection.face_analytics import FaceAnalyticsProcessor


def test_face_evidence_is_not_created_from_an_unverified_person_box():
    """A uniform person crop contains no face and must not produce face evidence."""
    processor = FaceAnalyticsProcessor()
    frame = np.zeros((160, 100, 3), dtype=np.uint8)

    result = processor.detect_face_in_person(frame, [20, 20, 80, 140])

    assert result is None
