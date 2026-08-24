"""
Border Intelligence Evidence Snapshot Extractor & Archival Module.
Persists visual JPEG snapshot frames with bounding box evidence for incident audits.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import cv2
import numpy as np
from pydantic import BaseModel, Field

from backend.config import get_settings


class SnapshotMetadata(BaseModel):
    snapshot_id: str
    incident_id: str
    camera_id: str
    frame_number: int
    trigger_reason: str
    file_path: str
    file_uri: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


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
    ) -> SnapshotMetadata:
        """Save a surveillance snapshot image with optional annotated target boxes."""
        snap_id = f"SNAP_{incident_id}_{frame_number}_{int(datetime.now().timestamp())}"
        filename = f"{snap_id}.jpg"
        file_path = self.snapshot_dir / filename

        # Annotate image if bounding boxes are provided
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

    def list_snapshots(self, incident_id: str) -> List[SnapshotMetadata]:
        """List all visual snapshot images associated with an incident."""
        prefix = f"SNAP_{incident_id}_"
        snapshots = []
        for p in self.snapshot_dir.glob(f"{prefix}*.jpg"):
            snapshots.append(
                SnapshotMetadata(
                    snapshot_id=p.stem,
                    incident_id=incident_id,
                    camera_id="CAM-01",
                    frame_number=0,
                    trigger_reason="PERIMETER_BREACH_EVIDENCE",
                    file_path=str(p),
                    file_uri=f"/api/evidence/snapshots/file/{p.name}",
                )
            )
        return snapshots


global_snapshot_manager = SnapshotArchiveManager()


def get_snapshot_manager() -> SnapshotArchiveManager:
    return global_snapshot_manager
