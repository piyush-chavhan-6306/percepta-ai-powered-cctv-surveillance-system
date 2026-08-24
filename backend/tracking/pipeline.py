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

from backend.detection.detector import DetectionResult, ObjectDetector, get_detector
from backend.events.schema import AlertEvent, DetectionEvent, TrackingEvent, ZoneEvent
from backend.events.store import EventStore, get_event_store
from backend.ingestion.adapter import FrameData
from backend.tracking.bytetrack_wrapper import ByteTrackTracker
from backend.tracking.tracker import BaseTracker, TrackedObject
from backend.zones.security_zone import ZoneMonitor

logger = logging.getLogger(__name__)


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
    ) -> None:
        self.detector = detector or get_detector()
        self.tracker = tracker or ByteTrackTracker()
        self.zone_monitor = zone_monitor or ZoneMonitor()
        self.event_store = event_store or get_event_store()
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

    def set_frame_overhead_ms(self, overhead_ms: float) -> None:
        """
        Report the out-of-pipeline cost of delivering one frame.

        The live worker calls this each cycle with its measured read + annotate +
        encode time so adaptive stride decisions are made against the rate the
        operator actually sees rather than inference latency alone.
        """
        self._frame_overhead_ms = max(0.0, float(overhead_ms))

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
            "total_pipeline_latency_ms": round(self._last_total_ms, 2),
            "total_latency_ms": round(self._last_total_ms, 2),
            "total_detections": self._total_detections,
            "alerts": self._total_alerts,
            "total_alerts": self._total_alerts,
            "active_tracks": len(self._last_tracks),
            "frame_stride": self.frame_stride,
            "adaptive_stride_enabled": self.adaptive_stride_enabled,
            "device": getattr(self.detector, "device", "cpu"),
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
                    events_to_persist = list(zone_events) + list(alert_events)
                    await self.event_store.record_events_batch(events_to_persist, publish=True)
                    self._total_alerts += len(alert_events)

                t_end = time.perf_counter()
                self._last_total_ms = (t_end - t0) * 1000.0
                self._last_inference_ms = 0.0
                self._last_persistence_ms = 0.0
                self._record_latency(self._last_total_ms)
                self._evaluate_adaptive_stride()

                return FrameProcessingResult(
                    frame_number=frame.frame_number,
                    detections=[],  # No fake YOLO detections
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
        detections = await self._detect_async(frame.image)
        t_det_end = time.perf_counter()
        self._last_inference_ms = (t_det_end - t_det_start) * 1000.0

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

        # 5. Persist all frame events atomically in single SQLite WAL transaction (Persist-Before-Publish)
        events_to_persist = []
        if detection_events:
            events_to_persist.extend(detection_events)
        if tracking_events:
            events_to_persist.extend(tracking_events)
        events_to_persist.extend(zone_events)
        events_to_persist.extend(alert_events)

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
