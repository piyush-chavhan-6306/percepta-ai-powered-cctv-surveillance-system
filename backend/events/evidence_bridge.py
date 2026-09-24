"""
PERCEPTA Evidence Bridge — EventBus → Incident + Evidence DB Pipeline.

Subscribes to the EventBus and listens for ALERT events.  When an alert is
received that carries snapshot evidence URIs, the bridge:

  1. Creates or updates an Incident record via IncidentManager.process_event()
  2. Computes SHA-256 hashes of the ACTUAL evidence image files on disk
  3. Creates Evidence records (full_scene, face_crop, plate_crop) via
     IncidentManager.attach_target_evidence()

This closes the critical gap where snapshot JPEGs were written to disk and
their URIs embedded in AlertEvent payloads, but no Incident or Evidence DB
records were ever created.

DESIGN RULES:
  - Fire-and-forget: failures here never block or crash the perception loop.
  - Atomic: Evidence records are only created after the file SHA-256 is
    verified readable.
  - Idempotent: re-processing the same alert is harmless (incident
    deduplication handles it).
"""
from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import Optional

from backend.config import get_settings
from backend.events.bus import EventBus, get_event_bus
from backend.events.schema import AlertEvent, BaseEvent, EventType
from backend.incidents.service import IncidentManager, get_incident_manager

logger = logging.getLogger(__name__)


def _sha256_file(file_path: Path) -> Optional[str]:
    """Compute SHA-256 of an actual file on disk.  Returns hex digest or None."""
    try:
        if not file_path.exists() or file_path.stat().st_size == 0:
            return None
        h = hashlib.sha256()
        with open(file_path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception as err:
        logger.warning(f"SHA-256 computation failed for {file_path}: {err}")
        return None


def _uri_to_disk_path(uri: Optional[str]) -> Optional[Path]:
    """Convert an evidence URI like '/api/evidence/snapshots/file/SNAP_xxx.jpg'
    to the on-disk Path inside the snapshots directory."""
    if not uri:
        return None
    # Extract filename from the URI
    filename = uri.rsplit("/", 1)[-1] if "/" in uri else uri
    settings = get_settings()
    snap_dir = Path(os.path.join(settings.STORAGE_DIR, "snapshots"))
    candidate = snap_dir / filename
    return candidate if candidate.exists() else None


class EvidenceBridge:
    """Bridges EventBus ALERT events to the Incident + Evidence persistence layer."""

    def __init__(
        self,
        bus: Optional[EventBus] = None,
        manager: Optional[IncidentManager] = None,
    ) -> None:
        self.bus = bus or get_event_bus()
        self.manager = manager or get_incident_manager()
        self._subscribed = False

    async def subscribe(self) -> None:
        """Register with the EventBus.  Safe to call multiple times."""
        if self._subscribed:
            return
        await self.bus.subscribe(self._on_event, event_type=EventType.ALERT)
        self._subscribed = True
        logger.info("EvidenceBridge subscribed to EventBus ALERT events")

    async def _on_event(self, event: BaseEvent) -> None:
        """Handle incoming events from the bus."""
        if not isinstance(event, AlertEvent):
            return
        try:
            await self._process_alert(event)
        except Exception as err:
            logger.error(f"EvidenceBridge failed to process alert {event.event_id}: {err}")

    async def _process_alert(self, alert: AlertEvent) -> None:
        """Create Incident + Evidence records for a single AlertEvent."""
        # ── 1. Create / update Incident via IncidentManager ──
        threat_score = alert.threat_score or 0.0
        threat_level = alert.threat_level or "NORMAL"
        threat_reasons = alert.threat_reasons or []
        zone_id = None
        zone_name = None

        # Extract zone info from the alert metadata if available
        meta = {}
        if hasattr(alert, "model_dump"):
            try:
                meta = alert.model_dump(mode="json")
            except Exception:
                pass

        incident, db_alert, is_new = await self.manager.process_event(
            event_type=alert.severity or "SECURITY_ALERT",
            camera_id=alert.camera_id,
            threat_score=threat_score,
            threat_level=threat_level,
            threat_reasons=threat_reasons,
            global_entity_id=alert.global_person_id,
            local_track_id=alert.track_id,
            zone_id=zone_id,
            zone_name=zone_name,
            timestamp=alert.timestamp,
            narrative=alert.message,
            metadata={
                "alert_event_id": str(alert.event_id),
                "evidence_snapshot_uri": alert.evidence_snapshot_uri,
                "face_snapshot_uri": alert.face_snapshot_uri,
                "anpr_snapshot_uri": alert.anpr_snapshot_uri,
                "modality": alert.modality,
            },
        )

        if not incident:
            return

        incident_id = incident.incident_id

        # ── 2. Attach FULL SCENE evidence ──
        scene_uri = alert.evidence_snapshot_uri
        scene_path = _uri_to_disk_path(scene_uri)
        if scene_path:
            scene_hash = _sha256_file(scene_path)
            if scene_hash:
                await self.manager.attach_target_evidence(
                    incident_id=incident_id,
                    target_entity_id=alert.global_person_id,
                    camera_id=alert.camera_id,
                    evidence_type="full_scene",
                    full_scene_path=str(scene_path),
                    confidence=alert.confidence or 0.9,
                    quality=1.0,
                    reason=f"Full scene snapshot: {alert.message or 'Security alert'}",
                    local_track_id=alert.track_id,
                    frame_number=alert.best_frame_number,
                    timestamp=alert.timestamp,
                )
                logger.info(
                    f"Evidence attached: full_scene for incident {incident_id} "
                    f"[SHA-256: {scene_hash[:16]}…]"
                )

        # ── 3. Attach FACE CROP evidence ──
        face_uri = alert.face_snapshot_uri
        face_path = _uri_to_disk_path(face_uri)
        if face_path:
            face_hash = _sha256_file(face_path)
            if face_hash:
                await self.manager.attach_target_evidence(
                    incident_id=incident_id,
                    target_entity_id=alert.global_person_id,
                    camera_id=alert.camera_id,
                    evidence_type="face_crop",
                    target_crop_path=str(face_path),
                    confidence=alert.face_confidence or 0.0,
                    quality=1.0,
                    reason="Face detection evidence crop",
                    local_track_id=alert.track_id,
                    frame_number=alert.best_frame_number,
                    timestamp=alert.timestamp,
                )

        # ── 4. Attach PLATE CROP evidence ──
        plate_uri = alert.anpr_snapshot_uri
        plate_path = _uri_to_disk_path(plate_uri)
        if plate_path:
            plate_hash = _sha256_file(plate_path)
            if plate_hash:
                await self.manager.attach_target_evidence(
                    incident_id=incident_id,
                    target_entity_id=alert.global_person_id,
                    camera_id=alert.camera_id,
                    evidence_type="plate_crop",
                    target_crop_path=str(plate_path),
                    confidence=alert.plate_confidence or 0.0,
                    quality=1.0,
                    reason=f"ANPR plate crop: {alert.plate_number or 'unreadable'}",
                    local_track_id=alert.track_id,
                    frame_number=alert.best_frame_number,
                    timestamp=alert.timestamp,
                )

        if is_new:
            logger.info(
                f"EvidenceBridge: NEW incident {incident_id} created from alert {alert.event_id}"
            )


# ── Singleton ──
_global_bridge: Optional[EvidenceBridge] = None


def get_evidence_bridge() -> EvidenceBridge:
    global _global_bridge
    if _global_bridge is None:
        _global_bridge = EvidenceBridge()
    return _global_bridge
