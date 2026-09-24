"""
Border Intelligence Tracking & Intelligence Pipeline Module.
Coordinates the end-to-end flow:
FrameData -> ObjectDetector -> ByteTrackTracker -> ZoneMonitor -> EventStore -> EventBus.
"""
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import time
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np

from backend.detection.detector import DetectionResult, ObjectDetector, get_detector
from backend.events.schema import AlertEvent, DetectionEvent, SourceType, TrackingEvent, ZoneEvent
from backend.events.store import EventStore, get_event_store
from backend.events.debouncer import EventDebouncer, get_event_debouncer
from backend.ingestion.adapter import FrameData
from backend.persistence.normalized_store import NormalizedStore, get_normalized_store
from backend.tracking.bytetrack_wrapper import ByteTrackTracker
from backend.tracking.tracker import BaseTracker, TrackedObject
from backend.zones.security_zone import ZoneMonitor

logger = logging.getLogger(__name__)


def _stamp_global_ids(
    tracks: List[TrackedObject],
    camera_id: str,
    frame_image: Optional[np.ndarray],
    frame_number: int = 0,
    frame_fps: float = 0.0,
    frame_source: Optional[SourceType] = None,
    normalized_store: Optional["NormalizedStore"] = None,
    session_id: Optional[str] = None,
) -> None:
    """
    Attach cross-camera Re-ID identities to person tracks (in place).

    Runs BETWEEN tracking and zone evaluation so every downstream event
    (tracking telemetry, zone entries, alerts) already carries the global id.
    Embedding crops are sampled at most once per ~1 s per track via
    observe_if_due; the label lookup is per-frame and cheap. Any Re-ID failure
    is contained: perception continues identically without it.
    """
    persons = [t for t in tracks if t.object_class == "person"]
    if not persons or frame_image is None:
        return
    try:
        from backend.tracking.reid_manager import get_reid_manager
        mgr = get_reid_manager()
    except Exception:
        return
    if not mgr.enabled:
        return
    # Video-file sources use MEDIA time for the Re-ID temporal windows so
    # replays/loops do not expire identities by wall clock. Live sources pass
    # ts=None and use the wall clock inside the manager.
    from backend.events.schema import SourceType
    media_ts: Optional[float] = None
    if frame_source == SourceType.VIDEO_FILE and frame_fps > 0:
        media_ts = float(frame_number) / float(frame_fps)
    for t in persons:
        try:
            decision = mgr.observe_if_due(camera_id, t.track_id, frame_image, t.bounding_box, ts=media_ts)
            gid = mgr.get_global_id(camera_id, t.track_id)
            t.global_person_id = gid or ""
            if gid:
                summary = mgr.get_identity_summary(gid)
                t.global_person_confirmed = bool(summary and summary.get("confirmed", False))
            else:
                t.global_person_confirmed = False

            # Persist global entity and cross-camera transitions
            if normalized_store and gid:
                confirmed = t.global_person_confirmed
                now = t.timestamp if hasattr(t, "timestamp") else None
                entity_uuid = normalized_store.upsert_global_entity(
                    display_id=gid,
                    entity_type="person",
                    camera_id=camera_id,
                    local_track_id=str(t.track_id),
                    timestamp=now,
                    confirmed=confirmed,
                    meta={"observation_count": summary.get("observations", 0) if summary else 0},
                )
                # Record cross-camera transition if this is a match on a new camera
                if decision and decision.matched and decision.score > 0:
                    prev_cameras = summary.get("cameras", []) if summary else []
                    if len(prev_cameras) > 1:
                        # Find the previous camera (not current)
                        prev_cameras = [c for c in prev_cameras if c != camera_id]
                        if prev_cameras:
                            prev_cam = prev_cameras[-1]
                            prev_local = summary.get("local_ids", {}).get(prev_cam, "")
                            normalized_store.create_camera_transition(
                                global_entity_id=entity_uuid or gid,
                                from_camera_id=prev_cam,
                                from_local_track_id=prev_local,
                                to_camera_id=camera_id,
                                to_local_track_id=str(t.track_id),
                                association_confidence=decision.score,
                                transition_time=now,
                                association_signals={
                                    "score": decision.score,
                                    "margin": decision.margin,
                                    "reason": decision.reason,
                                },
                            )
        except Exception:
            continue


@dataclass
class FrameProcessingResult:
    """Consolidated results of running one frame through the intelligence pipeline."""
    frame_number: int
    detections: List[DetectionResult]
    tracks: List[TrackedObject]
    zone_events: List[ZoneEvent]
    alert_events: List[AlertEvent]
    tracking_events: List[TrackingEvent]
    inference_latency_ms: float = 0.0
    tracking_latency_ms: float = 0.0
    persistence_latency_ms: float = 0.0
    total_latency_ms: float = 0.0


class TrackingPipeline:
    """
    Unified multi-object tracking and movement intelligence pipeline.
    Enforces Persist-Before-Publish at every stage with comprehensive telemetry.
    """

    def __init__(
        self,
        detector: Optional[ObjectDetector] = None,
        tracker: Optional[BaseTracker] = None,
        zone_monitor: Optional[ZoneMonitor] = None,
        event_store: Optional[EventStore] = None,
        normalized_store: Optional[NormalizedStore] = None,
        session_id: Optional[str] = None,
        emit_detection_events: bool = False,
        emit_tracking_events: bool = True,
        frame_stride: int = 1,
        target_fps: float = 25.0,
        min_frame_stride: int = 1,
        max_frame_stride: int = 3,
        adaptive_stride_enabled: bool = False,
        sample_window: int = 15,
        cooldown_frames: int = 30,
        enable_intermediate_predictions: bool = True,
        inference_lock: Optional["asyncio.Lock"] = None,
        tracking_event_interval_frames: int = 10,
        async_detection: bool = False,
        enable_tamper_detection: bool = False,
        detection_write_interval: int = 5,
    ) -> None:
        self.detector = detector or get_detector()
        self.tracker = tracker or ByteTrackTracker()
        self.zone_monitor = zone_monitor or ZoneMonitor()
        self.event_store = event_store or get_event_store()
        self.normalized_store = normalized_store or get_normalized_store()
        self.session_id = session_id
        self.detection_write_interval = max(1, detection_write_interval)
        self.event_debouncer = get_event_debouncer()
        self.emit_detection_events = emit_detection_events
        self.emit_tracking_events = emit_tracking_events
        self.frame_stride = max(1, frame_stride)
        self.target_fps = target_fps
        self.min_frame_stride = min_frame_stride
        self.max_frame_stride = max_frame_stride
        self.adaptive_stride_enabled = adaptive_stride_enabled
        self.sample_window = sample_window
        self.cooldown_frames = cooldown_frames
        self.enable_intermediate_predictions = enable_intermediate_predictions
        self.inference_lock = inference_lock
        self.async_detection = async_detection
        self.enable_tamper_detection = enable_tamper_detection
        self._async_detection_task: Optional[asyncio.Task] = None
        # Tracking events are pure telemetry (heatmaps, incident dossiers, replay)
        # and every visible object emits one per detection frame. At ~10 tracks
        # and 12 detection fps that is ~10M rows/day -- the DB grew 154 MB in an
        # hour of demo footage. Sampling every Nth frame *per track* keeps the
        # trajectory shape (and the heatmap) while bounding growth ~10x. Alerts
        # and zone events are never sampled: those must be exact.
        self.tracking_event_interval_frames = max(1, tracking_event_interval_frames)
        self._last_track_event_frame: Dict[int, int] = {}
        self._is_initialized = False

        # Telemetry & Metrics
        self._frames_processed = 0
        self._frames_skipped = 0
        self._frames_predicted = 0
        self._total_detections = 0
        self._total_alerts = 0
        self._last_inference_ms = 0.0
        self._last_tracking_ms = 0.0
        self._last_prediction_ms = 0.0
        self._last_persistence_ms = 0.0
        self._last_evidence_ms = 0.0
        self._last_total_ms = 0.0
        self._start_time = time.perf_counter()
        self._last_tracks: List[TrackedObject] = []
        self._cooldown_counter = 0
        self._recent_latencies: list[float] = []
        # Per-frame cost the pipeline itself cannot see (frame read, annotate,
        # JPEG encode). The stride controller must include it or it optimizes a
        # metric that excludes ~17 ms of every frame and settles one stride too
        # low. Callers that only run the pipeline leave this at 0.
        self._frame_overhead_ms = 0.0
        # Evidence collection throttle: cap per-frame cost and skip recently
        # processed tracks so identical crops are not re-inferred every frame.
        self._evidence_last_frame: Dict[str, int] = {}
        self._evidence_cache: Dict[str, dict] = {}  # cached evidence per track during cooldown
        self._EVIDENCE_COOLDOWN_FRAMES = 15
        self._MAX_EVIDENCE_PER_FRAME = 3
        # Throttled normalized table writes (detections + local_tracks)
        self._last_detection_write_frame = 0
        self._detection_writes_total = 0

    def set_frame_overhead_ms(self, overhead_ms: float) -> None:
        """
        Report the out-of-pipeline cost of delivering one frame.

        The live worker calls this each cycle with its measured read + annotate +
        encode time so adaptive stride decisions are made against the rate the
        operator actually sees rather than inference latency alone.
        """
        self._frame_overhead_ms = max(0.0, float(overhead_ms))

    def set_session(self, session_id: Optional[str]) -> None:
        """Update the active session ID (called by live_worker on session lifecycle)."""
        self.session_id = session_id

    def _write_normalized_batch(
        self,
        camera_id: str,
        frame_number: int,
        timestamp: datetime,
        detections: List[Any],
        tracks: List[Any],
    ) -> None:
        """
        Write detection and tracking data to normalized tables (sync, from worker thread).
        Throttled: detections written every `detection_write_interval` frames.
        Tracks upserted every frame (lightweight UPDATE/INSERT).
        """
        if not self.session_id:
            return

        # Always upsert local tracks (these are cheap updates)
        tracks_map = {}
        for t in tracks:
            tid = str(t.track_id) if hasattr(t, "track_id") else None
            if tid:
                tracks_map[tid] = t
                self.normalized_store.upsert_local_track(
                    self.session_id, camera_id, t,
                )

        # Throttle detection writes to avoid DB flooding
        if frame_number - self._last_detection_write_frame >= self.detection_write_interval:
            if detections:
                count = self.normalized_store.write_detections(
                    self.session_id, camera_id, frame_number, timestamp,
                    detections, tracks_map,
                )
                self._detection_writes_total += count
            self._last_detection_write_frame = frame_number

    def initialize(self) -> None:
        """Initialize detector and tracker."""
        if not self._is_initialized:
            self.detector.initialize()
            self.tracker.initialize()
            self._is_initialized = True
            logger.info("TrackingPipeline initialized successfully.")

    def reset(self) -> None:
        """Reset internal pipeline states."""
        self.tracker.reset()
        self.zone_monitor.reset()
        self._last_tracks = []
        self._frames_processed = 0
        self._frames_skipped = 0
        self._frames_predicted = 0
        self._cooldown_counter = 0
        self._recent_latencies.clear()
        self._last_track_event_frame.clear()
        self._start_time = time.perf_counter()

    def get_metrics(self) -> Dict[str, Any]:
        """Return comprehensive operational pipeline telemetry."""
        elapsed = time.perf_counter() - self._start_time
        total_frames = self._frames_processed + self._frames_skipped
        fps = (total_frames / elapsed) if elapsed > 0 else 0.0
        return {
            "processed_frames": self._frames_processed,
            "frames_processed": self._frames_processed,
            "skipped_frames": self._frames_skipped,
            "frames_skipped": self._frames_skipped,
            "predicted_frames": self._frames_predicted,
            "ai_processing_fps": round(fps, 2),
            "processing_fps": round(fps, 2),
            "inference_latency_ms": round(self._last_inference_ms, 2),
            "tracking_latency_ms": round(self._last_tracking_ms, 2),
            "prediction_latency_ms": round(self._last_prediction_ms, 2),
            "persistence_latency_ms": round(self._last_persistence_ms, 2),
            "evidence_latency_ms": round(self._last_evidence_ms, 2),
            "total_pipeline_latency_ms": round(self._last_total_ms, 2),
            "total_latency_ms": round(self._last_total_ms, 2),
            "total_detections": self._total_detections,
            "alerts": self._total_alerts,
            "total_alerts": self._total_alerts,
            "active_tracks": len(self._last_tracks),
            "frame_stride": self.frame_stride,
            "adaptive_stride_enabled": self.adaptive_stride_enabled,
            "device": getattr(self.detector, "device", "cpu"),
            "session_id": self.session_id,
            "detection_writes_total": self._detection_writes_total,
        }

    def _record_latency(self, latency_ms: float) -> None:
        """
        Append a latency sample, keeping the buffer bounded.

        This list is appended to on every single frame, so an unbounded list leaks
        steadily during 24/7 operation (~25 fps == ~2M floats/day). Only the most
        recent `sample_window` samples are ever read by the adaptive-stride logic.
        """
        self._recent_latencies.append(latency_ms)
        cap = max(self.sample_window * 4, 64)
        if len(self._recent_latencies) > cap:
            del self._recent_latencies[:-cap]

    def _should_emit_track_event(self, track: TrackedObject, frame_number: int) -> bool:
        """
        Decide whether this track's telemetry is due to be persisted.

        Always emits the first sighting and any lifecycle transition, so a track
        appearing, being lost, or being re-acquired is never missed. Between those
        it samples every `tracking_event_interval_frames`.
        """
        last = self._last_track_event_frame.get(track.track_id)
        if last is None:
            return True
        # "updated" is the steady state; created/recovered/lost/terminated are all
        # transitions worth recording exactly.
        if getattr(track, "lifecycle", "updated") != "updated":
            return True
        return (frame_number - last) >= self.tracking_event_interval_frames

    def _evaluate_adaptive_stride(self) -> None:
        """
        Evaluate processing speed and adaptively adjust frame stride with hysteresis and cooldown.
        Avoids rapid oscillation.
        """
        if not self.adaptive_stride_enabled:
            return

        if self._cooldown_counter > 0:
            self._cooldown_counter -= 1
            return

        if len(self._recent_latencies) < self.sample_window:
            return

        mean_lat_ms = sum(self._recent_latencies[-self.sample_window:]) / self.sample_window

        # `_recent_latencies` holds one sample per *displayed* frame, so it already
        # averages cheap prediction frames in with expensive detection frames.
        # Multiplying by frame_stride here would count the stride saving twice and
        # report a wildly optimistic rate: at stride 2 with 67 ms detections and
        # 0.2 ms predictions the mean is 33.6 ms, which is a true 29.8 fps, but
        # scaling by the stride claimed 59.5 fps. That over-report tripped the
        # "performance recovered" branch, dropped the stride back to 1, measured
        # 14.9 fps, raised it again, and oscillated forever -- pinning real output
        # at roughly half the achievable frame rate.
        #
        # `_frame_overhead_ms` charges each delivered frame its read + annotate +
        # encode cost as well, so the controller targets the rate the operator
        # actually sees rather than inference latency in isolation.
        cycle_ms = mean_lat_ms + self._frame_overhead_ms
        effective_fps = (1000.0 / cycle_ms) if cycle_ms > 0 else 0.0

        if effective_fps < self.target_fps * 0.85 and self.frame_stride < self.max_frame_stride:
            old_stride = self.frame_stride
            self.frame_stride += 1
            self._cooldown_counter = self.cooldown_frames
            logger.info(
                f"Adaptive frame stride increased {old_stride} -> {self.frame_stride}: "
                f"measured effective FPS ({effective_fps:.1f}) is below target ({self.target_fps:.1f})"
            )
        elif effective_fps > self.target_fps * 1.40 and self.frame_stride > self.min_frame_stride:
            old_stride = self.frame_stride
            self.frame_stride -= 1
            self._cooldown_counter = self.cooldown_frames
            logger.info(
                f"Adaptive frame stride decreased {old_stride} -> {self.frame_stride}: "
                f"measured effective FPS ({effective_fps:.1f}) recovered above target ({self.target_fps:.1f})"
            )

    def _attach_alert_evidence(
        self,
        alert_events: List[AlertEvent],
        frame: FrameData,
        tracks: List[TrackedObject],
    ) -> None:
        """
        Guarantee that EVERY alert event has visual forensic evidence attached (100% guarantee).

        Face and plate evidence come from REAL detectors (YuNet / YOLOv8n-plate /
        PP-OCRv3), not the old heuristic region crops. Crops are always taken
        from the ORIGINAL unmasked frame: live-view privacy masking happens at
        render time only and must never destroy the forensic copy. The multi-
        frame plate consensus (PlateEvidenceCollector) outranks a single weak
        OCR read; weak reads are flagged uncertain instead of guessed.
        """
        if not alert_events or frame is None or frame.image is None or frame.image.size == 0:
            return

        from backend.events.snapshots import get_snapshot_manager
        from backend.detection.evidence_detectors import get_face_detector, get_plate_recognizer
        from backend.detection.plate_aggregator import get_plate_collector
        snap_mgr = get_snapshot_manager()
        tracks_by_id = {str(t.track_id): t for t in tracks}

        evidence_count = 0
        for alert in alert_events:
            if getattr(alert, "evidence_snapshot_uri", None):
                continue

            t = tracks_by_id.get(str(alert.track_id))
            t_box = t.bounding_box if t else None
            face_b = None
            plate_b = None
            face_crop = None
            plate_crop = None
            face_conf = 0.0
            plate_text = ""
            plate_conf = 0.0
            plate_uncertain = False

            # Per-track cooldown: skip re-inference if processed recently,
            # but still try to attach existing evidence from prior processing.
            track_key = f"{frame.camera_id}:{alert.track_id}"
            last_frame = self._evidence_last_frame.get(track_key, -999)
            in_cooldown = (frame.frame_number - last_frame < self._EVIDENCE_COOLDOWN_FRAMES)

            # Hard cap on evidence per frame to bound latency
            if evidence_count >= self._MAX_EVIDENCE_PER_FRAME:
                break

            # ---- REAL face evidence for person tracks -------------------
            if not in_cooldown and t and t_box and len(t_box) >= 4 and t.object_class == "person":
                from backend.detection.evidence_detectors import FaceDetector as _FD
                try:
                    face = get_face_detector().best_face_in_box(frame.image, t_box, min_face_px=8)
                except Exception as fd_err:
                    logger.debug(f"Face detection failed on alert {alert.event_id}: {fd_err}")
                    face = None
                if face is not None:
                    face_b = face["bbox"]
                    face_conf = face["confidence"]
                    face_crop = _FD.crop_face_evidence(frame.image, face_b)

            # ---- REAL plate evidence for vehicle tracks -----------------
            # Thermal/IR frames carry no readable RGB plates: the plate model is
            # trained on visible-light imagery, so OCR there would be noise.
            # ANPR runs on STANDARD/RGB modality only, honestly.
            modality = (getattr(frame, "modality", "STANDARD") or "STANDARD").upper()
            if (
                not in_cooldown
                and t and t_box and len(t_box) >= 4
                and t.object_class in ("car", "truck", "bus", "motorcycle", "bicycle", "vehicle")
                and modality in ("STANDARD", "RGB")
            ):
                track_key = f"{frame.camera_id}:{t.track_id}"
                collector = get_plate_collector()
                detected_plate = None
                try:
                    detected_plate = get_plate_recognizer().detect_in_vehicle(frame.image, t_box)
                except Exception as pd_err:
                    logger.debug(f"Plate detection failed on alert {alert.event_id}: {pd_err}")
                if detected_plate is not None:
                    plate_b = detected_plate["bbox"]
                    reading = get_plate_recognizer().read_plate(frame.image, plate_b)
                    plate_crop = reading.get("crop_bgr")
                    plate_text = reading.get("text", "")
                    plate_conf = reading.get("confidence", 0.0)
                    sharp = float(cv2.Laplacian(
                        cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY), cv2.CV_64F
                    ).var()) if plate_crop is not None and plate_crop.size else 0.0
                    # Record this observation, then let the multi-frame
                    # consensus decide the stored result.
                    if plate_text:
                        collector.add_observation(
                            track_key=track_key,
                            text=plate_text,
                            confidence=plate_conf,
                            frame_number=frame.frame_number,
                            timestamp=frame.timestamp,
                            sharpness=sharp,
                            vehicle_box=list(t_box[:4]),
                            plate_box=list(plate_b[:4]),
                        )
                    consensus = collector.get_best(track_key)
                    if consensus is not None and (
                        not plate_text or consensus.confidence > plate_conf
                    ):
                        plate_text = consensus.text
                        plate_conf = consensus.confidence
                        plate_uncertain = consensus.uncertain
                    else:
                        plate_uncertain = reading.get("uncertain", True)

            if getattr(alert, "target_bbox", None) is None and t_box:
                alert.target_bbox = list(t_box)

            try:
                if in_cooldown and track_key in self._evidence_cache:
                    # Reuse cached evidence during cooldown
                    cached = self._evidence_cache[track_key]
                    alert.evidence_snapshot_uri = cached.get("evidence_uri")
                    alert.face_snapshot_uri = cached.get("face_uri")
                    alert.anpr_snapshot_uri = cached.get("anpr_uri")
                    alert.plate_number = cached.get("plate_text")
                    alert.plate_confidence = cached.get("plate_conf")
                    alert.plate_uncertain = cached.get("plate_uncertain", False)
                    alert.face_confidence = cached.get("face_conf")
                    evidence_count += 1
                else:
                    evidence = snap_mgr.create_evidence_package_async(
                        incident_id=str(alert.event_id),
                        image=frame.image,
                        camera_id=frame.camera_id,
                        frame_number=frame.frame_number,
                        trigger_reason=alert.message or "SECURITY_BREACH",
                        bounding_boxes=[tr.bounding_box for tr in tracks if tr.bounding_box],
                        face_bbox=face_b,
                        plate_bbox=plate_b,
                        confidence=alert.confidence or 0.9,
                        face_crop=face_crop,
                        plate_crop=plate_crop,
                        face_conf=face_conf,
                        plate_text=plate_text,
                        plate_conf=plate_conf,
                        plate_uncertain=plate_uncertain,
                    )
                    alert.evidence_snapshot_uri = evidence.file_uri
                    alert.face_snapshot_uri = evidence.face_snapshot_uri
                    alert.anpr_snapshot_uri = evidence.anpr_snapshot_uri
                    alert.plate_number = plate_text or None
                    alert.plate_confidence = plate_conf or None
                    alert.plate_uncertain = plate_uncertain
                alert.face_confidence = face_conf or None
                evidence_count += 1
                self._evidence_last_frame[track_key] = frame.frame_number
                # Cache evidence for reuse during cooldown
                self._evidence_cache[track_key] = {
                    "evidence_uri": alert.evidence_snapshot_uri,
                    "face_uri": alert.face_snapshot_uri,
                    "anpr_uri": alert.anpr_snapshot_uri,
                    "plate_text": alert.plate_number,
                    "plate_conf": alert.plate_confidence,
                    "plate_uncertain": alert.plate_uncertain,
                    "face_conf": alert.face_confidence,
                }
            except Exception as err:
                logger.warning(f"Evidence capture failed for alert {alert.event_id}: {err}")

    async def _detect_async(self, image) -> List[DetectionResult]:
        """
        Run YOLO inference without stalling the asyncio event loop.

        Inference is compute-bound and costs tens of milliseconds, so it runs in a
        worker thread; blocking the loop here would freeze every MJPEG client and
        WebSocket broadcast for the duration. When multiple cameras share a single
        detector instance, an optional lock serializes access because the
        underlying model is not re-entrant.
        """
        if self.inference_lock is not None:
            async with self.inference_lock:
                return await asyncio.to_thread(self.detector.detect, image)
        return await asyncio.to_thread(self.detector.detect, image)

    async def process_frame(
        self,
        frame: FrameData,
    ) -> FrameProcessingResult:
        """
        Process a single FrameData package through detection, tracking, zone analysis, and persistence.
        """
        if not self._is_initialized:
            self.initialize()

        if frame is None or frame.image is None:
            return FrameProcessingResult(
                frame_number=0 if frame is None else frame.frame_number,
                detections=[],
                tracks=[],
                zone_events=[],
                alert_events=[],
                tracking_events=[],
            )

        # Intermediate frame processing (advance tracker state via Kalman velocity prediction without YOLO)
        if self.frame_stride > 1 and ((frame.frame_number - 1) % self.frame_stride != 0):
            self._frames_skipped += 1
            t0 = time.perf_counter()

            if self.enable_intermediate_predictions and self._last_tracks:
                t_track_start = time.perf_counter()
                predicted_tracks = self.tracker.predict_step(frame)
                t_track_end = time.perf_counter()
                self._last_tracking_ms = (t_track_end - t_track_start) * 1000.0
                self._last_prediction_ms = self._last_tracking_ms
                self._frames_predicted += 1
                if predicted_tracks:
                    self._last_tracks = predicted_tracks

                # Evaluate security zones on predicted positions
                zone_events, alert_events = self.zone_monitor.evaluate_tracks(
                    tracks=self._last_tracks,
                    camera_id=frame.camera_id,
                    source=frame.source,
                )

                if zone_events or alert_events:
                    if alert_events:
                        self._attach_alert_evidence(alert_events, frame, self._last_tracks)
                        self._total_alerts += len(alert_events)
                    events_to_persist = list(zone_events) + list(alert_events)
                    asyncio.create_task(self.event_store.record_events_batch(events_to_persist, publish=True))

                t_end = time.perf_counter()
                self._last_total_ms = (t_end - t0) * 1000.0
                self._last_inference_ms = 0.0
                self._last_persistence_ms = 0.0
                self._record_latency(self._last_total_ms)
                self._evaluate_adaptive_stride()

                return FrameProcessingResult(
                    frame_number=frame.frame_number,
                    detections=[],
                    tracks=self._last_tracks,
                    zone_events=zone_events,
                    alert_events=alert_events,
                    tracking_events=[],
                    inference_latency_ms=0.0,
                    tracking_latency_ms=self._last_tracking_ms,
                    persistence_latency_ms=0.0,
                    total_latency_ms=self._last_total_ms,
                )
            else:
                return FrameProcessingResult(
                    frame_number=frame.frame_number,
                    detections=[],
                    tracks=self._last_tracks,
                    zone_events=[],
                    alert_events=[],
                    tracking_events=[],
                )

        t0 = time.perf_counter()

        # 1. Detect objects in frame (offloaded to a thread so the event loop stays responsive)
        t_det_start = time.perf_counter()
        from backend.ingestion.sensor_adapter import SensorFrameAdapter
        norm_image = SensorFrameAdapter.normalize_frame(frame.image, modality=getattr(frame, "modality", "STANDARD"))
        detections = await self._detect_async(norm_image)
        t_det_end = time.perf_counter()
        self._last_inference_ms = (t_det_end - t_det_start) * 1000.0
        self._total_detections += len(detections)

        # Optional: emit detection events
        detection_events: List[DetectionEvent] = []
        if self.emit_detection_events and detections:
            for det in detections:
                det_event = DetectionEvent(
                    camera_id=frame.camera_id,
                    object_class=det.class_name,
                    bounding_box=det.bounding_box,
                    frame_number=frame.frame_number,
                    confidence=det.confidence,
                    source=frame.source,
                    timestamp=frame.timestamp,
                )
                detection_events.append(det_event)

        # 2. Update multi-object tracker
        t_track_start = time.perf_counter()
        tracks = self.tracker.update(detections, frame)
        t_track_end = time.perf_counter()
        self._last_tracking_ms = (t_track_end - t_track_start) * 1000.0
        self._last_tracks = tracks

        # 2.5 Attach cross-camera person identities (Re-ID layer, sampled ~1/s)
        _stamp_global_ids(tracks, frame.camera_id, frame.image,
                          frame.frame_number, frame.fps, frame.source,
                          normalized_store=self.normalized_store, session_id=self.session_id)

        # 3. Create tracking events
        tracking_events: List[TrackingEvent] = []
        if self.emit_tracking_events and tracks:
            live_ids = set()
            for track in tracks:
                live_ids.add(track.track_id)
                if not self._should_emit_track_event(track, frame.frame_number):
                    continue
                self._last_track_event_frame[track.track_id] = frame.frame_number
                track_event = TrackingEvent(
                    camera_id=frame.camera_id,
                    track_id=track.track_id,
                    global_person_id=track.global_person_id or None,
                    confidence=track.confidence,
                    source=frame.source,
                    timestamp=track.timestamp,
                    lifecycle=track.lifecycle,
                    position=[track.center_x, track.center_y],
                    velocity=[track.velocity[0], track.velocity[1]],
                    object_class=track.object_class,
                    bounding_box=track.bounding_box,
                    frame_number=track.frame_number,
                    speed=track.speed_px_per_frame,
                    direction=track.direction_deg,
                )
                tracking_events.append(track_event)

            # Drop bookkeeping for tracks that no longer exist, so this dict
            # cannot grow without bound across a 24/7 run.
            if len(self._last_track_event_frame) > len(live_ids):
                for stale in [tid for tid in self._last_track_event_frame if tid not in live_ids]:
                    del self._last_track_event_frame[stale]

        # 4. Evaluate security zones and virtual boundaries
        zone_events, alert_events = self.zone_monitor.evaluate_tracks(
            tracks=tracks,
            camera_id=frame.camera_id,
            source=frame.source,
        )

        # 4.5 Propagate global person ids onto zone/alert events so persisted
        # history links camera-local tracks with cross-camera identities.
        _tracks_by_id = {str(t.track_id): t for t in tracks}
        for _ev in list(zone_events) + list(alert_events):
            _t = _tracks_by_id.get(str(getattr(_ev, "track_id", None)))
            if _t is not None:
                _ev.global_person_id = _t.global_person_id or None

        # Check for camera sabotage / physical tampering (occlusion, laser blinding, spray paint)
        if self.enable_tamper_detection and frame.source != SourceType.SIMULATION:
            from backend.detection.tamper import get_tamper_detector
            tamper_res = get_tamper_detector(frame.camera_id).evaluate_frame(frame.image, camera_id=frame.camera_id)
            if tamper_res.is_tampered:
                from backend.events.schema import AlertEvent
                tamper_alert = AlertEvent(
                    camera_id=frame.camera_id,
                    severity="CRITICAL",
                    threat_level="CRITICAL",
                    threat_score=95.0,
                    threat_reasons=tamper_res.reasons,
                    message=f"CAMERA TAMPER DETECTED: {', '.join(tamper_res.reasons)}",
                    timestamp=frame.timestamp,
                    source=frame.source,
                )
                alert_events.append(tamper_alert)

        if alert_events:
            self._attach_alert_evidence(alert_events, frame, tracks)

        # 5. Persist frame events asynchronously in background task (Non-blocking high-FPS streaming)
        events_to_persist = []
        if detection_events:
            events_to_persist.extend(detection_events)
        if tracking_events:
            events_to_persist.extend(tracking_events)
        # Debounce zone events to prevent flooding
        debounced_zone = [
            ze for ze in zone_events
            if self.event_debouncer.should_emit(
                f"zone_{ze.transition}", ze.camera_id,
                track_id=getattr(ze, "track_id", None),
                zone_id=ze.zone_id,
            )
        ]
        events_to_persist.extend(debounced_zone)
        events_to_persist.extend(alert_events)

        # 5.5 Write normalized detections + local_tracks (sync, from worker thread)
        self._write_normalized_batch(
            frame.camera_id, frame.frame_number, frame.timestamp, detections, tracks,
        )

        t_db_start = time.perf_counter()
        if events_to_persist:
            await self.event_store.record_events_batch(events_to_persist, publish=True)
            self._total_alerts += len(alert_events)
        t_db_end = time.perf_counter()
        self._last_persistence_ms = (t_db_end - t_db_start) * 1000.0

        t_end = time.perf_counter()
        self._last_total_ms = (t_end - t0) * 1000.0
        self._frames_processed += 1
        self._total_detections += len(detections)

        # Performance Watchdog & Adaptive Stride Evaluation
        self._record_latency(self._last_total_ms)
        self._evaluate_adaptive_stride()

        return FrameProcessingResult(
            frame_number=frame.frame_number,
            detections=detections,
            tracks=tracks,
            zone_events=zone_events,
            alert_events=alert_events,
            tracking_events=tracking_events,
            inference_latency_ms=self._last_inference_ms,
            tracking_latency_ms=self._last_tracking_ms,
            persistence_latency_ms=self._last_persistence_ms,
            total_latency_ms=self._last_total_ms,
        )

    def process_frame_sync(self, frame: FrameData) -> FrameProcessingResult:
        """
        Synchronous version of process_frame for use in thread pool workers.
        Runs YOLO detection + tracking directly (no asyncio).
        Skips persistence to avoid DB contention from background threads.
        Returns tracks and detections for the render pipeline.
        """
        if not self._is_initialized:
            self.initialize()

        if frame is None or frame.image is None:
            return FrameProcessingResult(
                frame_number=0 if frame is None else frame.frame_number,
                detections=[], tracks=[], zone_events=[],
                alert_events=[], tracking_events=[],
            )

        # Intermediate frame processing (advance tracker state via Kalman velocity prediction without YOLO)
        if self.frame_stride > 1 and ((frame.frame_number - 1) % self.frame_stride != 0):
            self._frames_skipped += 1
            t0 = time.perf_counter()

            if self.enable_intermediate_predictions and self._last_tracks:
                t_track_start = time.perf_counter()
                predicted_tracks = self.tracker.predict_step(frame)
                t_track_end = time.perf_counter()
                self._last_tracking_ms = (t_track_end - t_track_start) * 1000.0
                self._last_prediction_ms = self._last_tracking_ms
                self._frames_predicted += 1
                if predicted_tracks:
                    self._last_tracks = predicted_tracks

                # Evaluate security zones on predicted positions
                zone_events, alert_events = self.zone_monitor.evaluate_tracks(
                    tracks=self._last_tracks,
                    camera_id=frame.camera_id,
                    source=frame.source,
                )

                if alert_events:
                    self._attach_alert_evidence(alert_events, frame, self._last_tracks)
                    self._total_alerts += len(alert_events)

                self._last_inference_ms = 0.0
                self._last_total_ms = (time.perf_counter() - t0) * 1000.0
                self._record_latency(self._last_total_ms)

                return FrameProcessingResult(
                    frame_number=frame.frame_number,
                    detections=[],
                    tracks=self._last_tracks,
                    zone_events=zone_events,
                    alert_events=alert_events,
                    tracking_events=[],
                    inference_latency_ms=0.0,
                    tracking_latency_ms=self._last_tracking_ms,
                    total_latency_ms=self._last_total_ms,
                )

        # --- Multi-Modal Normalization via SensorFrameAdapter ---
        from backend.ingestion.sensor_adapter import SensorFrameAdapter
        modality = getattr(frame, "modality", "STANDARD")
        norm_image = SensorFrameAdapter.normalize_frame(frame.image, modality=modality)

        # --- YOLO Detection (synchronous, runs in worker thread) ---
        t_det_start = time.perf_counter()
        detections = self.detector.detect(norm_image)
        t_det_end = time.perf_counter()
        self._last_inference_ms = (t_det_end - t_det_start) * 1000.0
        self._total_detections += len(detections)

        # --- ByteTrack update ---
        t_track_start = time.perf_counter()
        tracks = self.tracker.update(detections, frame)
        t_track_end = time.perf_counter()
        self._last_tracking_ms = (t_track_end - t_track_start) * 1000.0
        self._last_tracks = tracks

        # --- Cross-camera person identity (Re-ID layer, sampled ~1/s per track) ---
        _stamp_global_ids(tracks, frame.camera_id, frame.image,
                          frame.frame_number, frame.fps, frame.source,
                          normalized_store=self.normalized_store, session_id=self.session_id)

        # --- Zone evaluation (lightweight, sync-safe) ---
        zone_events, alert_events = self.zone_monitor.evaluate_tracks(
            tracks=tracks, camera_id=frame.camera_id, source=frame.source,
        )

        # Propagate global person ids onto zone/alert events (see async path).
        _tracks_by_id = {str(t.track_id): t for t in tracks}
        for _ev in list(zone_events) + list(alert_events):
            _t = _tracks_by_id.get(str(getattr(_ev, "track_id", None)))
            if _t is not None:
                _ev.global_person_id = _t.global_person_id or None

        # Check for camera sabotage / physical tampering (occlusion, laser blinding, spray paint)
        if self.enable_tamper_detection and frame.source != SourceType.SIMULATION:
            from backend.detection.tamper import get_tamper_detector
            tamper_res = get_tamper_detector(frame.camera_id).evaluate_frame(frame.image, camera_id=frame.camera_id)
            if tamper_res.is_tampered:
                from backend.events.schema import AlertEvent
                tamper_alert = AlertEvent(
                    camera_id=frame.camera_id,
                    severity="CRITICAL",
                    threat_level="CRITICAL",
                    threat_score=95.0,
                    threat_reasons=tamper_res.reasons,
                    message=f"CAMERA TAMPER DETECTED: {', '.join(tamper_res.reasons)}",
                    timestamp=frame.timestamp,
                    source=frame.source,
                )
                alert_events.append(tamper_alert)

        # Capture forensic evidence snapshots for alert events (non-blocking async)
        t_ev_start = time.perf_counter()
        if alert_events:
            self._attach_alert_evidence(alert_events, frame, tracks)
            self._total_alerts += len(alert_events)
        t_ev_end = time.perf_counter()
        # Track last evidence_ms directly as a private attribute for debuggers
        self._last_evidence_ms = (t_ev_end - t_ev_start) * 1000.0

        t_end = time.perf_counter()
        self._last_total_ms = (t_end - t_det_start) * 1000.0
        self._frames_processed += 1

        # Write normalized detections + local_tracks (sync, from worker thread)
        self._write_normalized_batch(
            frame.camera_id, frame.frame_number, frame.timestamp, detections, tracks,
        )

        #region debug-point: PIPELINE sync detail every 30 frames
        if frame.frame_number % 30 == 0:
            det_ms = (t_det_end - t_det_start) * 1000.0
            trk_ms = (t_track_end - t_track_start) * 1000.0
            ev_ms = self._last_evidence_ms
            fps = (self._frames_processed / (time.perf_counter() - self._start_time)) if (time.perf_counter() - self._start_time) > 0 else 0.0
            logger.info(
                f"[PIPELINE-SYNC] {frame.camera_id} frame={frame.frame_number} "
                f"detection_ms={det_ms:.1f} tracking_ms={trk_ms:.1f} evidence_ms={ev_ms:.1f} "
                f"total_ms={self._last_total_ms:.1f} processing_fps={fps:.1f} "
                f"detections={len(detections)} tracks={len(tracks)} alerts={len(alert_events)} zone={len(zone_events)}"
            )
        #endregion

        # Record latency for adaptive stride controller
        self._record_latency(self._last_total_ms)
        self._evaluate_adaptive_stride()

        return FrameProcessingResult(
            frame_number=frame.frame_number,
            detections=detections,
            tracks=tracks,
            zone_events=zone_events,
            alert_events=alert_events,
            tracking_events=[],
            inference_latency_ms=self._last_inference_ms,
            tracking_latency_ms=self._last_tracking_ms,
            persistence_latency_ms=0.0,
            total_latency_ms=self._last_total_ms,
        )
