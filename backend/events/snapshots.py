"""
Border Intelligence Evidence Snapshot Extractor & Archival Module.
Persists visual JPEG snapshot frames, face crops, and license plate crops with bounding box evidence.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import cv2
import numpy as np
from pydantic import BaseModel, Field

from backend.config import get_settings

logger = logging.getLogger(__name__)
_evidence_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="evidence_writer")


class SnapshotMetadata(BaseModel):
    snapshot_id: str
    incident_id: str
    camera_id: str
    frame_number: int
    trigger_reason: str
    file_path: str
    file_uri: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EvidencePackageMetadata(BaseModel):
    snapshot_id: str
    incident_id: str
    camera_id: str
    frame_number: int
    trigger_reason: str
    file_path: str
    file_uri: str
    face_snapshot_uri: Optional[str] = None
    anpr_snapshot_uri: Optional[str] = None
    sharpness_score: float = 0.0
    confidence: float = 0.0
    modality: str = "STANDARD"
    plate_text: Optional[str] = None
    plate_confidence: float = 0.0
    plate_uncertain: bool = False
    face_confidence: float = 0.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BestEvidenceFrameSelector:
    """
    Evaluates candidate stream frames during an incident to identify the highest-quality
    forensic evidence frame based on target confidence, optical sharpness (Laplacian variance),
    and bounding box visibility.
    """

    @staticmethod
    def calculate_sharpness(image: np.ndarray) -> float:
        """Compute Laplacian variance representing image sharpness / focus."""
        if image is None or image.size == 0:
            return 0.0
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())

    @classmethod
    def score_frame_quality(
        cls,
        image: np.ndarray,
        confidence: float,
        bbox: Optional[List[float]] = None,
    ) -> float:
        """Composite quality metric (0.0 to 100.0)."""
        sharpness = cls.calculate_sharpness(image)
        # Normalize sharpness (50-500 typical range mapped to 0-1)
        sharp_norm = min(max(sharpness / 300.0, 0.0), 1.0)
        conf_norm = min(max(confidence, 0.0), 1.0)

        # Center/size weight
        size_norm = 0.5
        if bbox and len(bbox) >= 4 and image is not None:
            h, w = image.shape[:2]
            bw = bbox[2] - bbox[0]
            bh = bbox[3] - bbox[1]
            box_area = (bw * bh) / max(w * h, 1)
            size_norm = min(box_area * 10.0, 1.0)

        composite = (0.45 * conf_norm + 0.35 * sharp_norm + 0.20 * size_norm) * 100.0
        return round(composite, 2)


class SnapshotArchiveManager:
    """Manages saving, indexing, and serving visual snapshot evidence for incident dossiers."""

    def __init__(self, snapshot_dir: Optional[str] = None) -> None:
        settings = get_settings()
        self.snapshot_dir = Path(snapshot_dir or os.path.join(settings.STORAGE_DIR, "snapshots"))
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

    def save_snapshot(
        self,
        incident_id: str,
        image: np.ndarray,
        camera_id: str = "CAM-01",
        frame_number: int = 0,
        trigger_reason: str = "RESTRICTED_ZONE_BREACH",
        bounding_boxes: Optional[List[List[float]]] = None,
        modality: str = "STANDARD",
    ) -> SnapshotMetadata:
        """Save a surveillance snapshot image with optional annotated target boxes."""
        snap_id = f"SNAP_{incident_id}_{frame_number}_{int(datetime.now().timestamp())}"
        filename = f"{snap_id}.jpg"
        file_path = self.snapshot_dir / filename

        annotated = image.copy() if image is not None else np.zeros((480, 640, 3), dtype=np.uint8)
        if bounding_boxes and image is not None:
            for box in bounding_boxes:
                if len(box) >= 4:
                    x1, y1, x2, y2 = map(int, box[:4])
                    cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 0, 255), 2)
                    cv2.putText(
                        annotated,
                        "TARGET EVIDENCE",
                        (x1, max(y1 - 5, 15)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 0, 255),
                        1,
                    )

        cv2.imwrite(str(file_path), annotated)

        return SnapshotMetadata(
            snapshot_id=snap_id,
            incident_id=incident_id,
            camera_id=camera_id,
            frame_number=frame_number,
            trigger_reason=trigger_reason,
            file_path=str(file_path),
            file_uri=f"/api/evidence/snapshots/file/{filename}",
        )

    def save_multi_evidence_package(
        self,
        incident_id: str,
        image: np.ndarray,
        camera_id: str = "CAM-01",
        frame_number: int = 0,
        trigger_reason: str = "RESTRICTED_ZONE_BREACH",
        bounding_boxes: Optional[List[List[float]]] = None,
        face_bbox: Optional[List[float]] = None,
        plate_bbox: Optional[List[float]] = None,
        confidence: float = 0.9,
        modality: str = "STANDARD",
    ) -> EvidencePackageMetadata:
        """
        Generate and persist Full Scene Evidence + Face Evidence Crop + ANPR Plate Crop.
        """
        snap_meta = self.save_snapshot(
            incident_id=incident_id,
            image=image,
            camera_id=camera_id,
            frame_number=frame_number,
            trigger_reason=trigger_reason,
            bounding_boxes=bounding_boxes,
            modality=modality,
        )

        face_uri = None
        plate_uri = None
        sharpness = BestEvidenceFrameSelector.calculate_sharpness(image)

        if image is not None and image.size > 0:
            h, w = image.shape[:2]

            # 1. Face Evidence Snapshot Crop
            if face_bbox and len(face_bbox) >= 4:
                fx1, fy1, fx2, fy2 = map(int, face_bbox[:4])
                fx1, fy1 = max(0, fx1), max(0, fy1)
                fx2, fy2 = min(w, fx2), min(h, fy2)
                if fx2 > fx1 and fy2 > fy1:
                    face_crop = image[fy1:fy2, fx1:fx2]
                    face_fname = f"FACE_{snap_meta.snapshot_id}.jpg"
                    face_fpath = self.snapshot_dir / face_fname
                    cv2.imwrite(str(face_fpath), face_crop)
                    face_uri = f"/api/evidence/snapshots/file/{face_fname}"

            # 2. ANPR License Plate Evidence Crop
            if plate_bbox and len(plate_bbox) >= 4:
                px1, py1, px2, py2 = map(int, plate_bbox[:4])
                px1, py1 = max(0, px1), max(0, py1)
                px2, py2 = min(w, px2), min(h, py2)
                if px2 > px1 and py2 > py1:
                    plate_crop = image[py1:py2, px1:px2]
                    plate_fname = f"ANPR_{snap_meta.snapshot_id}.jpg"
                    plate_fpath = self.snapshot_dir / plate_fname
                    cv2.imwrite(str(plate_fpath), plate_crop)
                    plate_uri = f"/api/evidence/snapshots/file/{plate_fname}"

        return EvidencePackageMetadata(
            snapshot_id=snap_meta.snapshot_id,
            incident_id=incident_id,
            camera_id=camera_id,
            frame_number=frame_number,
            trigger_reason=trigger_reason,
            file_path=snap_meta.file_path,
            file_uri=snap_meta.file_uri,
            face_snapshot_uri=face_uri,
            anpr_snapshot_uri=plate_uri,
            sharpness_score=round(sharpness, 1),
            confidence=confidence,
            modality=modality,
        )

    save_multi_evidence_package_nowait = save_multi_evidence_package
    save_snapshot_with_crops = save_multi_evidence_package

    def create_evidence_package_async(
        self,
        incident_id: str,
        image: np.ndarray,
        camera_id: str = "CAM-01",
        frame_number: int = 0,
        trigger_reason: str = "RESTRICTED_ZONE_BREACH",
        bounding_boxes: Optional[List[List[float]]] = None,
        face_bbox: Optional[List[float]] = None,
        plate_bbox: Optional[List[float]] = None,
        confidence: float = 0.9,
        modality: str = "STANDARD",
        face_crop: Optional[np.ndarray] = None,
        plate_crop: Optional[np.ndarray] = None,
        face_conf: float = 0.0,
        plate_text: str = "",
        plate_conf: float = 0.0,
        plate_uncertain: bool = False,
    ) -> EvidencePackageMetadata:
        """
        Immediately returns EvidencePackageMetadata with deterministic URIs,
        while offloading physical image writing to a background thread.
        Guarantees zero latency penalty on the real-time inference/render loop.

        `face_crop` / `plate_crop` are pre-cut evidence crops produced by the
        real face/plate detectors. When supplied they are written verbatim —
        the bbox path is only used as a fallback so legacy callers keep working.
        """
        snap_id = f"SNAP_{incident_id}_{frame_number}_{int(datetime.now().timestamp())}"
        filename = f"{snap_id}.jpg"
        file_path = self.snapshot_dir / filename
        file_uri = f"/api/evidence/snapshots/file/{filename}"

        face_uri = None
        face_fpath = None
        if (face_crop is not None and face_crop.size > 0) or (
            face_bbox and len(face_bbox) >= 4 and image is not None and image.size > 0
        ):
            face_fname = f"FACE_{snap_id}.jpg"
            face_fpath = self.snapshot_dir / face_fname
            face_uri = f"/api/evidence/snapshots/file/{face_fname}"

        plate_uri = None
        plate_fpath = None
        if (plate_crop is not None and plate_crop.size > 0) or (
            plate_bbox and len(plate_bbox) >= 4 and image is not None and image.size > 0
        ):
            plate_fname = f"ANPR_{snap_id}.jpg"
            plate_fpath = self.snapshot_dir / plate_fname
            plate_uri = f"/api/evidence/snapshots/file/{plate_fname}"

        # Copy image for background disk write to avoid tearing
        if image is not None and image.size > 0:
            img_copy = image.copy()
            boxes_copy = [list(b) for b in (bounding_boxes or [])]
            face_crop_copy = face_crop.copy() if face_crop is not None and face_crop.size > 0 else None
            plate_crop_copy = plate_crop.copy() if plate_crop is not None and plate_crop.size > 0 else None
            _evidence_pool.submit(
                self._write_evidence_files,
                img_copy,
                file_path,
                boxes_copy,
                face_fpath,
                face_bbox,
                plate_fpath,
                plate_bbox,
                face_crop_copy,
                plate_crop_copy,
                plate_text,
            )

        return EvidencePackageMetadata(
            snapshot_id=snap_id,
            incident_id=incident_id,
            camera_id=camera_id,
            frame_number=frame_number,
            trigger_reason=trigger_reason,
            file_path=str(file_path),
            file_uri=file_uri,
            face_snapshot_uri=face_uri,
            anpr_snapshot_uri=plate_uri,
            sharpness_score=85.0,
            confidence=confidence,
            modality=modality,
            plate_text=plate_text or None,
            plate_confidence=plate_conf,
            plate_uncertain=plate_uncertain,
            face_confidence=face_conf,
        )

    @staticmethod
    def _write_evidence_files(
        image: np.ndarray,
        file_path: Path,
        bounding_boxes: List[List[float]],
        face_fpath: Optional[Path],
        face_bbox: Optional[List[float]],
        plate_fpath: Optional[Path],
        plate_bbox: Optional[List[float]],
        face_crop: Optional[np.ndarray] = None,
        plate_crop: Optional[np.ndarray] = None,
        plate_text: str = "",
    ) -> None:
        try:
            h, w = image.shape[:2]
            # 1. Face crop — detector-provided crop preferred over bbox slicing
            if face_fpath is not None:
                face_img = None
                if face_crop is not None and face_crop.size > 0:
                    face_img = face_crop
                elif face_bbox and len(face_bbox) >= 4:
                    fx1, fy1, fx2, fy2 = map(int, face_bbox[:4])
                    fx1, fy1 = max(0, fx1), max(0, fy1)
                    fx2, fy2 = min(w, fx2), min(h, fy2)
                    if fx2 > fx1 and fy2 > fy1:
                        face_img = image[fy1:fy2, fx1:fx2]
                if face_img is not None and face_img.size > 0:
                    cv2.imwrite(str(face_fpath), face_img)

            # 2. Plate crop — detector-provided crop preferred over bbox slicing
            if plate_fpath is not None:
                plate_img = None
                if plate_crop is not None and plate_crop.size > 0:
                    plate_img = plate_crop
                elif plate_bbox and len(plate_bbox) >= 4:
                    px1, py1, px2, py2 = map(int, plate_bbox[:4])
                    px1, py1 = max(0, px1), max(0, py1)
                    px2, py2 = min(w, px2), min(h, py2)
                    if px2 > px1 and py2 > py1:
                        plate_img = image[py1:py2, px1:px2]
                if plate_img is not None and plate_img.size > 0:
                    if plate_text:
                        # Burn the OCR reading onto the crop margin for offline review
                        bar_h = max(18, plate_img.shape[0] // 6)
                        bar = np.full((bar_h, plate_img.shape[1], 3), 30, np.uint8)
                        cv2.putText(
                            bar, plate_text, (4, bar_h - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (120, 255, 120), 1, cv2.LINE_AA,
                        )
                        plate_img = np.vstack([plate_img, bar])
                    cv2.imwrite(str(plate_fpath), plate_img)

            # 3. Full scene with red target boxes
            annotated = image.copy()
            for box in bounding_boxes:
                if len(box) >= 4:
                    bx1, by1, bx2, by2 = map(int, box[:4])
                    cv2.rectangle(annotated, (bx1, by1), (bx2, by2), (0, 0, 255), 2)
                    cv2.putText(
                        annotated,
                        "TARGET EVIDENCE",
                        (bx1, max(by1 - 5, 15)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 0, 255),
                        1,
                    )
            cv2.imwrite(str(file_path), annotated)
        except Exception as err:
            logger.warning(f"Background evidence write failed: {err}")

    async def save_snapshot_async(
        self,
        incident_id: str,
        image: np.ndarray,
        camera_id: str = "CAM-01",
        frame_number: int = 0,
        trigger_reason: str = "RESTRICTED_ZONE_BREACH",
        bounding_boxes: Optional[List[List[float]]] = None,
        modality: str = "STANDARD",
    ) -> SnapshotMetadata:
        """Asynchronously save a snapshot offloaded to worker thread to prevent event-loop stalls."""
        import asyncio
        return await asyncio.to_thread(
            self.save_snapshot,
            incident_id=incident_id,
            image=image,
            camera_id=camera_id,
            frame_number=frame_number,
            trigger_reason=trigger_reason,
            bounding_boxes=bounding_boxes,
            modality=modality,
        )

    async def save_multi_evidence_package_async(
        self,
        incident_id: str,
        image: np.ndarray,
        camera_id: str = "CAM-01",
        frame_number: int = 0,
        trigger_reason: str = "RESTRICTED_ZONE_BREACH",
        bounding_boxes: Optional[List[List[float]]] = None,
        face_bbox: Optional[List[float]] = None,
        plate_bbox: Optional[List[float]] = None,
        confidence: float = 0.9,
        modality: str = "STANDARD",
    ) -> EvidencePackageMetadata:
        """Asynchronously generate and persist full + face + ANPR evidence package."""
        import asyncio
        return await asyncio.to_thread(
            self.save_multi_evidence_package,
            incident_id=incident_id,
            image=image,
            camera_id=camera_id,
            frame_number=frame_number,
            trigger_reason=trigger_reason,
            bounding_boxes=bounding_boxes,
            face_bbox=face_bbox,
            plate_bbox=plate_bbox,
            confidence=confidence,
            modality=modality,
        )

    def list_snapshots(self, incident_id: str) -> List[SnapshotMetadata]:
        results = []
        for file in self.snapshot_dir.glob(f"SNAP_{incident_id}_*.jpg"):
            results.append(
                SnapshotMetadata(
                    snapshot_id=file.stem,
                    incident_id=incident_id,
                    camera_id="UNKNOWN",
                    frame_number=0,
                    trigger_reason="HISTORICAL",
                    file_path=str(file),
                    file_uri=f"/api/evidence/snapshots/file/{file.name}",
                )
            )
        return results


global_snapshot_manager = SnapshotArchiveManager()


def get_snapshot_manager() -> SnapshotArchiveManager:
    return global_snapshot_manager
