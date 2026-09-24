"""
PERCEPTA Defense — Normalized Table Persistence.

Thread-safe synchronous writes for detections, local_tracks, and sessions.
Uses a dedicated sync SQLite engine so the pipeline's ThreadPoolExecutor
can write without async overhead or contention with the async API layer.
"""
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from backend.database.schema import Camera, CameraTransition, Detection, GlobalEntity, LocalTrack, Session as SessionRow

logger = logging.getLogger(__name__)

_sync_engine = None
_sync_session_factory = None


def _get_sync_engine():
    """Lazy-init a synchronous SQLite engine for background writes."""
    global _sync_engine
    if _sync_engine is not None:
        return _sync_engine
    from backend.config import get_settings
    settings = get_settings()
    raw_url = settings.DATABASE_URL
    # Convert async driver URL to sync: sqlite+aiosqlite:/// -> sqlite:///
    sync_url = raw_url.replace("sqlite+aiosqlite:///", "sqlite:///")
    _sync_engine = create_engine(
        sync_url,
        echo=False,
        future=True,
        connect_args={"check_same_thread": False},
    )
    # Ensure WAL + busy timeout for concurrent access
    with _sync_engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL;"))
        conn.execute(text("PRAGMA busy_timeout=5000;"))
        conn.execute(text("PRAGMA synchronous=NORMAL;"))
        conn.commit()
    logger.info("NormalizedStore: sync engine initialized")
    return _sync_engine


def _get_session() -> Session:
    """Get a short-lived synchronous session."""
    global _sync_session_factory
    if _sync_session_factory is None:
        _sync_session_factory = sessionmaker(bind=_get_sync_engine(), expire_on_commit=False)
    return _sync_session_factory()


class NormalizedStore:
    """
    Writes detections, local tracks, and sessions to normalized tables.
    All methods are synchronous and safe to call from worker threads.
    """

    def ensure_camera(self, camera_id: str) -> None:
        """Ensure a Camera row exists (idempotent)."""
        if not camera_id:
            return
        try:
            db = _get_session()
            try:
                existing = db.query(Camera).filter(Camera.camera_id == camera_id).first()
                if existing is None:
                    db.add(Camera(camera_id=camera_id, name=camera_id, status="active"))
                    db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.debug(f"NormalizedStore.ensure_camera failed: {e}")

    def create_session(
        self,
        camera_id: str,
        fps: Optional[float] = None,
        resolution_w: Optional[int] = None,
        resolution_h: Optional[int] = None,
    ) -> Optional[str]:
        """Create a new processing session. Returns session_id."""
        try:
            db = _get_session()
            try:
                self.ensure_camera(camera_id)
                row = SessionRow(
                    camera_id=camera_id,
                    started_at=datetime.now(timezone.utc),
                    status="active",
                    fps=fps,
                    resolution_w=resolution_w,
                    resolution_h=resolution_h,
                )
                db.add(row)
                db.commit()
                session_id = row.session_id
                logger.info(f"NormalizedStore: session {session_id} created for camera {camera_id}")
                return session_id
            finally:
                db.close()
        except Exception as e:
            logger.error(f"NormalizedStore.create_session failed: {e}")
            return None

    def end_session(self, session_id: str) -> None:
        """Mark a session as ended."""
        if not session_id:
            return
        try:
            db = _get_session()
            try:
                row = db.query(SessionRow).filter(SessionRow.session_id == session_id).first()
                if row:
                    row.ended_at = datetime.now(timezone.utc)
                    row.status = "stopped"
                    db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.debug(f"NormalizedStore.end_session failed: {e}")

    def write_detections(
        self,
        session_id: str,
        camera_id: str,
        frame_number: int,
        timestamp: datetime,
        detections: List[Any],
        tracks_map: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Write Detection rows for a frame. Links detections to tracks via bbox overlap.
        Returns number of rows written.
        """
        if not detections or not session_id:
            return 0
        try:
            db = _get_session()
            try:
                rows = []
                for det in detections:
                    bbox = det.bounding_box if hasattr(det, "bounding_box") else det.get("bbox", [0,0,0,0])
                    class_name = det.class_name if hasattr(det, "class_name") else det.get("class_name", "unknown")
                    confidence = det.confidence if hasattr(det, "confidence") else det.get("confidence", 0.0)
                    norm = det.normalized_box if hasattr(det, "normalized_box") else det.get("norm", [0,0,0,0])

                    # Link to track by checking if track bbox overlaps this detection
                    linked_track_id = None
                    if tracks_map:
                        for tid, track in tracks_map.items():
                            tb = track.bounding_box if hasattr(track, "bounding_box") else [0,0,0,0]
                            if self._bbox_iou(bbox, tb) > 0.5:
                                linked_track_id = tid
                                break

                    row = Detection(
                        session_id=session_id,
                        camera_id=camera_id,
                        timestamp=timestamp,
                        frame_number=frame_number,
                        class_name=class_name,
                        confidence=confidence,
                        bbox_x1=float(bbox[0]),
                        bbox_y1=float(bbox[1]),
                        bbox_x2=float(bbox[2]),
                        bbox_y2=float(bbox[3]),
                        detector_source="yolov8n",
                        local_track_id=linked_track_id,
                    )
                    rows.append(row)

                db.bulk_save_objects(rows)
                db.commit()
                return len(rows)
            finally:
                db.close()
        except Exception as e:
            logger.debug(f"NormalizedStore.write_detections failed: {e}")
            return 0

    def upsert_local_track(
        self,
        session_id: str,
        camera_id: str,
        track: Any,
    ) -> None:
        """Upsert a LocalTrack row from a TrackedObject."""
        if not track or not session_id:
            return
        track_id = track.track_id if hasattr(track, "track_id") else None
        if not track_id:
            return
        try:
            db = _get_session()
            try:
                existing = db.query(LocalTrack).filter(
                    LocalTrack.local_track_id == str(track_id),
                    LocalTrack.camera_id == camera_id,
                ).first()

                # Build trajectory JSON
                trajectory = None
                if hasattr(track, "trajectory") and track.trajectory:
                    trajectory = [{"x": p[0], "y": p[1]} for p in track.trajectory]

                velocity = None
                if hasattr(track, "velocity") and track.velocity:
                    velocity = {"dx": track.velocity[0], "dy": track.velocity[1]}

                lifecycle = getattr(track, "lifecycle", "updated")
                status = "active" if lifecycle in ("created", "updated", "recovered") else "lost"
                if lifecycle == "terminated":
                    status = "terminated"

                now = datetime.now(timezone.utc)
                first_seen = getattr(track, "timestamp", now)
                last_seen = now

                if existing:
                    existing.last_seen = last_seen
                    existing.frame_count = getattr(track, "hits", existing.frame_count + 1)
                    existing.trajectory = trajectory or existing.trajectory
                    existing.velocity = velocity or existing.velocity
                    existing.status = status
                    existing.tracking_confidence = getattr(track, "confidence", existing.tracking_confidence)
                    existing.global_entity_id = getattr(track, "global_person_id", None) or existing.global_entity_id
                else:
                    row = LocalTrack(
                        local_track_id=str(track_id),
                        camera_id=camera_id,
                        session_id=session_id,
                        global_entity_id=getattr(track, "global_person_id", None) or None,
                        class_name=getattr(track, "object_class", "unknown"),
                        first_seen=first_seen,
                        last_seen=last_seen,
                        frame_count=getattr(track, "hits", 1),
                        trajectory=trajectory,
                        velocity=velocity,
                        status=status,
                        tracking_confidence=getattr(track, "confidence", 0.0),
                    )
                    db.add(row)

                db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.debug(f"NormalizedStore.upsert_local_track failed: {e}")

    def upsert_global_entity(
        self,
        display_id: str,
        entity_type: str = "person",
        camera_id: Optional[str] = None,
        local_track_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        confirmed: bool = False,
        meta: Optional[dict] = None,
    ) -> Optional[str]:
        """
        Upsert a GlobalEntity row. Returns global_entity_id.
        Called when Re-ID assigns or updates a global identity.
        """
        if not display_id:
            return None
        try:
            db = _get_session()
            try:
                now = timestamp or datetime.now(timezone.utc)
                existing = db.query(GlobalEntity).filter(
                    GlobalEntity.display_id == display_id
                ).first()

                if existing:
                    existing.last_seen = now
                    if camera_id:
                        existing.current_camera_id = camera_id
                    if local_track_id:
                        existing.current_local_track_id = local_track_id
                    if confirmed:
                        existing.meta = {**(existing.meta or {}), "confirmed": True}
                    if meta:
                        existing.meta = {**(existing.meta or {}), **meta}
                    db.commit()
                    return existing.global_entity_id
                else:
                    row = GlobalEntity(
                        display_id=display_id,
                        entity_type=entity_type,
                        first_seen=now,
                        last_seen=now,
                        current_camera_id=camera_id,
                        current_local_track_id=local_track_id,
                        status="active",
                        meta=meta or {},
                    )
                    db.add(row)
                    db.commit()
                    logger.info(f"NormalizedStore: GlobalEntity {display_id} created (type={entity_type})")
                    return row.global_entity_id
            finally:
                db.close()
        except Exception as e:
            logger.debug(f"NormalizedStore.upsert_global_entity failed: {e}")
            return None

    def create_camera_transition(
        self,
        global_entity_id: str,
        from_camera_id: str,
        from_local_track_id: str,
        to_camera_id: str,
        to_local_track_id: str,
        association_confidence: float,
        transition_time: Optional[datetime] = None,
        association_signals: Optional[dict] = None,
    ) -> Optional[str]:
        """
        Record a cross-camera transition. Returns transition_id.
        Called when Re-ID links a track from a new camera to an existing global identity.
        """
        if not global_entity_id:
            return None
        try:
            db = _get_session()
            try:
                row = CameraTransition(
                    global_entity_id=global_entity_id,
                    from_camera_id=from_camera_id,
                    from_local_track_id=from_local_track_id,
                    to_camera_id=to_camera_id,
                    to_local_track_id=to_local_track_id,
                    association_confidence=association_confidence,
                    transition_time=transition_time or datetime.now(timezone.utc),
                    association_signals=association_signals or {},
                )
                db.add(row)
                db.commit()
                logger.info(
                    f"NormalizedStore: transition {from_camera_id}/{from_local_track_id} "
                    f"-> {to_camera_id}/{to_local_track_id} (entity={global_entity_id}, "
                    f"conf={association_confidence:.2f})"
                )
                return row.transition_id
            finally:
                db.close()
        except Exception as e:
            logger.debug(f"NormalizedStore.create_camera_transition failed: {e}")
            return None

    @staticmethod
    def _bbox_iou(box_a: list, box_b: list) -> float:
        """Compute IoU between two [x1,y1,x2,y2] boxes."""
        if not box_a or not box_b or len(box_a) < 4 or len(box_b) < 4:
            return 0.0
        x1 = max(box_a[0], box_b[0])
        y1 = max(box_a[1], box_b[1])
        x2 = min(box_a[2], box_b[2])
        y2 = min(box_a[3], box_b[3])
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        area_a = max(0, box_a[2] - box_a[0]) * max(0, box_a[3] - box_a[1])
        area_b = max(0, box_b[2] - box_b[0]) * max(0, box_b[3] - box_b[1])
        union = area_a + area_b - inter
        return inter / union if union > 0 else 0.0


_store: Optional[NormalizedStore] = None


def get_normalized_store() -> NormalizedStore:
    global _store
    if _store is None:
        _store = NormalizedStore()
    return _store
