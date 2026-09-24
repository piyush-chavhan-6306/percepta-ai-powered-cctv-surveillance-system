"""
Border Intelligence Live Perception Worker.

One worker per camera owns the whole real-time path for that stream:

    read frame -> pipeline.process_frame -> annotate -> JPEG encode -> publish

The worker is the *single owner* of its frame source. `adapter.read_frame_blocking()`
advances the capture by one frame, so if two consumers both pulled from it they
would steal frames from each other and each see a stuttering half-rate stream.
Everything else in the process (MJPEG clients, snapshots) reads the annotated
JPEG this worker publishes.

Encoding happens once per frame no matter how many browsers are watching; clients
fan out from the shared `LiveFrame` slot rather than each re-encoding.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import time
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

from backend.config import get_settings
from backend.events.schema import SourceType
from backend.ingestion.camera_manager import CameraManager, CameraStatus, get_camera_manager
from backend.tracking.overlay import annotate_frame, draw_offline, encode_jpeg
from backend.tracking.pipeline import TrackingPipeline
from backend.zones.security_zone import ZoneMonitor, get_zone_monitor

logger = logging.getLogger(__name__)

# Dedicated thread pool for YOLO inference — separate from asyncio's default
# executor (which also handles render + read threads). Isolating inference
# prevents annotation/encoding from stealing CPU time from ONNX.
_inference_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="yolo")


@dataclass
class LiveFrame:
    """The most recent annotated frame published by a worker."""
    jpeg: bytes
    sequence: int
    frame_number: int
    track_count: int
    published_at: float


class CameraWorker:
    """Runs continuous perception for one camera and publishes annotated frames."""

    def __init__(
        self,
        camera_id: str,
        manager: Optional[CameraManager] = None,
        pipeline: Optional[TrackingPipeline] = None,
        target_fps: Optional[float] = None,
        jpeg_quality: int = 78,
        reconnect_max_delay: float = 20.0,
    ) -> None:
        settings = get_settings()
        self.camera_id = camera_id
        self.manager = manager or get_camera_manager()
        self.jpeg_quality = settings.MJPEG_JPEG_QUALITY or 60
        self.reconnect_max_delay = reconnect_max_delay

        # Private per-track state, shared zone/boundary definitions: a zone added
        # through /api/zones is picked up live, without cross-camera state bleed.
        self.zone_monitor: ZoneMonitor = ZoneMonitor.with_shared_definitions(get_zone_monitor())

        # Per-camera ONNX detector — no shared model, no inference lock needed.
        # Each camera runs YOLO independently at full speed.
        from backend.detection.onnx_detector import get_onnx_detector
        onnx_det = get_onnx_detector(camera_id)

        # Wrap ONNX detector with the ObjectDetector interface the pipeline expects
        from backend.detection.detector import ObjectDetector, DetectionResult
        class _OnnxAdapter(ObjectDetector):
            def __init__(self, onnx_det):
                self._onnx = onnx_det
                self._is_initialized = True
            @property
            def device(self):
                return getattr(self._onnx, "device", "cpu")
            @property
            def active_provider(self):
                return getattr(self._onnx, "active_provider", "CPUExecutionProvider")
            def detect(self, image):
                raw = self._onnx.detect(image)
                return [
                    DetectionResult(
                        class_id=d["class_id"],
                        class_name=d["class_name"],
                        confidence=d["confidence"],
                        bounding_box=d["bbox"],
                        normalized_box=d["norm"],
                    )
                    for d in raw
                ]
            def initialize(self):
                self._onnx.initialize()

        self.pipeline = pipeline or TrackingPipeline(
            detector=_OnnxAdapter(onnx_det),
            zone_monitor=self.zone_monitor,
            frame_stride=settings.DEFAULT_FRAME_STRIDE,  # YOLO on keyframes, Kalman prediction between them
            target_fps=30.0,
            min_frame_stride=1,
            max_frame_stride=settings.MAX_FRAME_STRIDE,
            adaptive_stride_enabled=True,
            sample_window=15,
            cooldown_frames=30,
            enable_intermediate_predictions=True,  # Kalman interpolation on intermediate frames
            enable_tamper_detection=True,  # VisionAI-Aegis lens occlusion and sabotage alert
            inference_lock=None,  # No lock — each camera has its own detector
        )

        self._target_fps = target_fps or 30.0
        self._task: Optional[asyncio.Task] = None
        self._stopping = False
        self._latest: Optional[LiveFrame] = None
        self._sequence = 0
        # Woken on every publish so MJPEG clients push frames as they are produced
        # instead of polling on a timer.
        self._frame_ready = asyncio.Event()

        self._display_fps = 0.0
        self._fps_window_start = time.perf_counter()
        self._fps_window_frames = 0
        self._consecutive_read_failures = 0
        self._reconnects = 0
        self._started_at: Optional[datetime] = None
        self._last_error: Optional[str] = None
        self._last_read_ms = 0.0
        self._last_render_ms = 0.0
        self._last_inference_ms = 0.0
        self._last_jpeg: Optional[bytes] = None
        self._inference_fps = 0.0
        self._inference_fps_window_start = time.perf_counter()
        self._inference_fps_window_count = 0
        self._last_activity_time = time.perf_counter()
        self._no_activity_alert_interval = 1800.0
        self._workers_heartbeat_last = time.perf_counter()
        self._session_id: Optional[str] = None
        self.is_paused: bool = False

    # ---------------------------------------------------------------- lifecycle

    def pause(self) -> None:
        """Pause perception and freeze frame streaming."""
        self.is_paused = True
        logger.info(f"Perception paused for camera '{self.camera_id}'")

    def resume(self) -> None:
        """Resume active perception."""
        self.is_paused = False
        logger.info(f"Perception resumed for camera '{self.camera_id}'")

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        """Start the perception loop (idempotent)."""
        if self.is_running:
            return
        self._stopping = False
        self._started_at = datetime.now(timezone.utc)
        self.pipeline.initialize()
        # Create normalized session
        try:
            from backend.persistence.normalized_store import get_normalized_store
            store = get_normalized_store()
            self._session_id = store.create_session(
                self.camera_id,
                fps=self._target_fps,
            )
            self.pipeline.set_session(self._session_id)
        except Exception as sess_err:
            logger.debug(f"Could not create normalized session: {sess_err}")
        self._task = asyncio.create_task(self._run(), name=f"perception:{self.camera_id}")
        logger.info(f"Perception worker started for camera '{self.camera_id}' session={self._session_id}")

    async def stop(self) -> None:
        """Cancel the loop and wait for it to unwind."""
        self._stopping = True
        task = self._task
        self._task = None
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception as err:  # pragma: no cover - defensive
                logger.warning(f"Perception worker for '{self.camera_id}' raised on shutdown: {err}")
        self._frame_ready.set()  # release any waiting MJPEG clients
        # End normalized session
        if self._session_id:
            try:
                from backend.persistence.normalized_store import get_normalized_store
                get_normalized_store().end_session(self._session_id)
            except Exception:
                pass
        # Explicitly release per-camera ONNX session to free native memory
        try:
            from backend.detection.onnx_detector import release_onnx_detector
            release_onnx_detector(self.camera_id)
        except Exception as onnx_err:
            logger.debug(f"Could not release ONNX detector for '{self.camera_id}': {onnx_err}")
        logger.info(f"Perception worker stopped for camera '{self.camera_id}' session={self._session_id}")

    # ----------------------------------------------------------------- consumers

    def get_latest(self) -> Optional[LiveFrame]:
        """Most recently published annotated frame, or None before the first one."""
        return self._latest

    async def wait_for_frame(self, after_sequence: int, timeout: float = 5.0) -> Optional[LiveFrame]:
        """
        Await the next frame newer than `after_sequence`.

        Event-driven rather than polled, so a viewer receives each frame as soon
        as it is encoded and an idle stream costs nothing. Returns None on
        timeout so the caller can re-check whether the camera is still alive.
        """
        latest = self._latest
        if latest is not None and latest.sequence > after_sequence:
            return latest
        try:
            await asyncio.wait_for(self._frame_ready.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            return None
        latest = self._latest
        if latest is not None and latest.sequence > after_sequence:
            return latest
        return None

    def get_metrics(self) -> Dict[str, Any]:
        """Real telemetry for this camera — every value measured, none assumed."""
        metrics = self.pipeline.get_metrics()
        latest = self._latest
        record = self.manager.get_camera(self.camera_id)
        adapter_info = record.adapter.get_stream_info() if record and hasattr(record.adapter, "get_stream_info") else {}
        source_fps = float(adapter_info.get("fps", self._target_fps or 30.0) or 30.0)

        metrics.update(
            {
                "camera_id": self.camera_id,
                "source_fps": round(source_fps, 2),
                "display_fps": round(self._display_fps, 2),
                "inference_fps": round(self._inference_fps, 2),
                "inference_latency_ms": round(self._last_inference_ms, 2),
                "device": str(metrics.get("device", "cpu")).upper(),
                "active_provider": getattr(self.pipeline.detector, "active_provider", "CPUExecutionProvider"),
                "track_count": len(self.pipeline.tracker.get_active_tracks()) if hasattr(self.pipeline, "tracker") else 0,
                "worker_running": self.is_running,
                "reconnects": self._reconnects,
                "published_frames": self._sequence,
                "last_frame_number": latest.frame_number if latest else 0,
                "jpeg_bytes": len(latest.jpeg) if latest else 0,
                "read_latency_ms": round(self._last_read_ms, 2),
                "encoding_latency_ms": round(self._last_render_ms, 2),
                "started_at": self._started_at.isoformat() if self._started_at else None,
                "last_error": self._last_error,
                "session_id": self._session_id,
            }
        )
        return metrics

    # --------------------------------------------------------------- internals

    async def _safe_record_events(self, evs: list) -> None:
        try:
            await self.pipeline.event_store.record_events_batch(evs, publish=True)
        except Exception as ev_err:
            logger.error(f"Failed to record live events: {ev_err}")

    def _publish(self, jpeg: bytes, frame_number: int, track_count: int) -> None:
        self._sequence += 1
        self._latest = LiveFrame(
            jpeg=jpeg,
            sequence=self._sequence,
            frame_number=frame_number,
            track_count=track_count,
            published_at=time.perf_counter(),
        )
        # Pulse the event: wake everyone waiting, then re-arm for the next frame.
        self._frame_ready.set()
        self._frame_ready.clear()

    def _tick_fps(self) -> None:
        """Measured output rate over a rolling ~1 s window."""
        self._fps_window_frames += 1
        elapsed = time.perf_counter() - self._fps_window_start
        if elapsed >= 1.0:
            self._display_fps = self._fps_window_frames / elapsed
            self._fps_window_frames = 0
            self._fps_window_start = time.perf_counter()

    def _render(self, image: np.ndarray, tracks: List[Any], degraded: bool = False) -> Optional[bytes]:
        """Annotate + encode. Runs in a worker thread: both steps are CPU-bound."""
        metrics = self.pipeline.get_metrics()
        record = self.manager.get_camera(self.camera_id)
        modality = record.modality if record else "STANDARD"
        privacy_masking = bool(getattr(record, "privacy_masking", False)) if record else False

        # Decouple display rendering canvas from raw frame buffer so live privacy
        # masking never mutates the original forensic evidence frame.
        render_img = image.copy()
        if modality == "THERMAL":
            from backend.detection.thermal_processor import get_thermal_processor
            render_img = get_thermal_processor().render_thermal_colormap(image)

        # Scale down 1080p+ display canvas to 720p for 10x faster JPEG compression (1.5ms vs 18ms)
        h, w = render_img.shape[:2]
        if w > 1280:
            target_w = 1280
            target_h = int(h * (1280.0 / w))
            render_img = cv2.resize(render_img, (target_w, target_h), interpolation=cv2.INTER_LINEAR)

        annotated = annotate_frame(
            render_img,
            tracks,
            zones=list(self.zone_monitor.zones.values()),
            boundaries=list(self.zone_monitor.boundaries.values()),
            camera_id=self.camera_id,
            display_fps=self._display_fps,
            inference_fps=metrics.get("ai_processing_fps"),
            device=str(metrics.get("device", "cpu")),
            stride=int(metrics.get("frame_stride", 1)),
            degraded=degraded,
            modality=modality,
            privacy_masking=privacy_masking,
        )
        return encode_jpeg(annotated, quality=self.jpeg_quality)

    async def _publish_offline_card(self, message: str) -> None:
        """Show an explicit signal-loss card instead of freezing on a stale frame."""
        record = self.manager.get_camera(self.camera_id)
        width, height = 1280, 720
        if record is not None:
            info = record.adapter.get_stream_info() if hasattr(record.adapter, "get_stream_info") else {}
            width = int(info.get("width") or 0) or 1280
            height = int(info.get("height") or 0) or 720

        canvas = np.zeros((height, width, 3), dtype=np.uint8)
        draw_offline(canvas, self.camera_id, message)
        jpeg = await asyncio.to_thread(encode_jpeg, canvas, self.jpeg_quality)
        if jpeg:
            self._publish(jpeg, frame_number=0, track_count=0)

    async def _reconnect(self) -> bool:
        """
        Re-open a dropped source with capped exponential backoff.

        Retries forever by design: a border camera that drops at 03:00 must come
        back on its own without a server restart (AC2). The delay is capped so a
        glitchy feed doesn't back off to a multi-minute blind spot.
        """
        self._reconnects += 1
        delay = 0.5
        attempt = 0
        while not self._stopping:
            attempt += 1
            await self._publish_offline_card(f"Reconnecting (attempt {attempt})...")
            ok = await self.manager.reconnect_camera(self.camera_id, max_retries=1, base_delay=0.1)
            if ok:
                logger.info(f"Camera '{self.camera_id}' back online after {attempt} attempts")
                self._last_error = None
                # A new capture means new object identities; keep IDs honest.
                self.pipeline.reset()
                # End old session, create new one
                if self._session_id:
                    try:
                        from backend.persistence.normalized_store import get_normalized_store
                        store = get_normalized_store()
                        store.end_session(self._session_id)
                        self._session_id = store.create_session(
                            self.camera_id, fps=self._target_fps,
                        )
                        self.pipeline.set_session(self._session_id)
                    except Exception:
                        pass
                return True

            record = self.manager.get_camera(self.camera_id)
            self._last_error = record.last_error if record else "camera deregistered"
            if record is None:
                return False

            logger.warning(
                f"Camera '{self.camera_id}' reconnect attempt {attempt} failed "
                f"({self._last_error}); retrying in {delay:.1f}s"
            )
            await asyncio.sleep(delay)
            delay = min(self.reconnect_max_delay, delay * 2)

        return False

    async def _run(self) -> None:
        """
        Decoupled perception loop: inference runs independently of display.

        Architecture:
          1. Read frames at source rate (30 FPS for LIVE sources)
          2. For FINITE VIDEO FILES (non-looping): read as fast as possible
          3. Kick off YOLO inference as a background task (does NOT block display)
          4. Render immediately using the LATEST available tracks
          5. When inference completes, update tracks for the next render

        Pacing policy:
          - LIVE sources (RTSP, webcam, simulation): throttle to source FPS
            so we don't buffer-blast a live stream faster than it produces.
          - Looping video file (loop=True): throttle to FPS for smooth loop
            playback so it doesn't spin at 100 FPS burning CPU.
          - Finite video file (loop=False, VIDEO_FILE): process as FAST AS
            POSSIBLE with NO artificial throttling. Border footage must be
            ingested completely before an operator can review it; real-time
            playback pacing here would turn a 5-min clip into a 5-min wait
            and manifest as "progress stuck at 4%".
        """
        record = self.manager.get_camera(self.camera_id)
        if record is None:
            logger.error(f"Perception worker for '{self.camera_id}' aborted: camera not registered")
            return

        adapter = record.adapter
        is_finite_video_file = (
            getattr(adapter, "source", None) == SourceType.VIDEO_FILE
            and not bool(getattr(adapter, "loop", False))
        )

        source_fps = float(self._target_fps or 30.0)
        frame_interval = 1.0 / source_fps if source_fps > 0 else 0.033
        enable_pacing = not is_finite_video_file
        max_read_failures = 15

        logger.info(
            f"Perception loop running for '{self.camera_id}' at up to {source_fps:.1f} fps "
            f"(decoupled inference/display, pacing={'ON' if enable_pacing else 'OFF for finite video'})"
        )

        next_deadline = time.perf_counter()

        # Shared state between inference and render (protected by asyncio single-thread)
        latest_tracks: list = []
        latest_detections: list = []
        inference_task: Optional[asyncio.Task] = None
        frames_read = 0
        frames_inferred = 0

        def _tick_inference_fps() -> None:
            nonlocal frames_inferred
            frames_inferred += 1

        try:
            while not self._stopping:
                if self.is_paused:
                    # Maintain MJPEG stream presence with the latest frame without advancing or running inference
                    if self._latest is not None:
                        self._frame_ready.set()
                        self._frame_ready.clear()
                    await asyncio.sleep(0.1)
                    continue

                cycle_start = time.perf_counter()

                frame = await self.manager.get_latest_frame(self.camera_id)
                self._last_read_ms = (time.perf_counter() - cycle_start) * 1000.0

                if frame is None or frame.image is None:
                    record = self.manager.get_camera(self.camera_id)
                    if record is None:
                        return  # deregistered underneath us

                    # Check if adapter reached EOF cleanly (non-looping video file)
                    is_eof = getattr(record.adapter, "_eof_reached", False) or (
                        getattr(record.adapter, "source", None) == SourceType.VIDEO_FILE
                        and not getattr(record.adapter, "loop", False)
                        and not record.adapter.is_running
                    )
                    if is_eof:
                        logger.info(f"Perception worker for '{self.camera_id}' reached EOF cleanly. Stopping perception loop.")
                        record.status = CameraStatus.OFFLINE
                        return

                    self._consecutive_read_failures += 1
                    source_dead = (
                        not record.adapter.is_running
                        or self._consecutive_read_failures >= max_read_failures
                    )
                    if source_dead:
                        if not await self._reconnect():
                            return
                    else:
                        await asyncio.sleep(0.02)
                    continue

                self._consecutive_read_failures = 0
                frames_read += 1

                # --- SYNCHRONIZED PERCEPTION & TRACKING ---
                # Every frame is processed in lockstep so Frame N is rendered with Frame N's exact tracks.
                # This completely eliminates the freeze-and-jump lag caused by desynchronized background inference.
                inf_start = time.perf_counter()
                loop = asyncio.get_running_loop()
                try:
                    res = await loop.run_in_executor(
                        _inference_executor,
                        self.pipeline.process_frame_sync,
                        frame,
                    )
                except Exception as inf_err:
                    logger.error(
                        f"[INFERENCE ERROR] Camera '{self.camera_id}', frame {frame.frame_number} failed: {inf_err}",
                        exc_info=True,
                    )
                    from backend.tracking.pipeline import FrameProcessingResult
                    res = FrameProcessingResult(
                        frame_number=frame.frame_number,
                        detections=[],
                        tracks=self.pipeline.tracker.get_active_tracks(),
                        zone_events=[],
                        alert_events=[],
                        tracking_events=[],
                    )

                self._last_inference_ms = (time.perf_counter() - inf_start) * 1000.0

                #region debug-point: PIPELINE per-frame detail latencies every 30 frames
                if frame.frame_number % 30 == 0:
                    pm = self.pipeline.get_metrics()
                    det_ms = float(pm.get("inference_latency_ms", 0.0))
                    trk_ms = float(pm.get("tracking_latency_ms", 0.0))
                    pred_ms = float(pm.get("prediction_latency_ms", 0.0))
                    ev_ms = float(pm.get("evidence_latency_ms", 0.0))
                    tot_ms = float(pm.get("total_pipeline_latency_ms", 0.0))
                    ingest_fps = (1000.0 / self._last_read_ms) if self._last_read_ms > 0 else 0.0
                    logger.info(
                        f"[PIPELINE] {self.camera_id} frame={frame.frame_number} "
                        f"ingest_fps={ingest_fps:.1f} inference_fps={self._inference_fps:.1f} "
                        f"detection_ms={det_ms:.1f} tracking_ms={trk_ms:.1f} prediction_ms={pred_ms:.1f} "
                        f"evidence_ms={ev_ms:.1f} encode_ms={self._last_render_ms:.1f} "
                        f"total_pipeline_ms={tot_ms:.1f} alerts_total={int(pm.get('total_alerts', 0))} "
                        f"tracks={len(res.tracks)} detections={len(res.detections)} "
                        f"alerts_this_frame={len(res.alert_events)}"
                    )
                #endregion
                self._inference_fps_window_count += 1
                elapsed = time.perf_counter() - self._inference_fps_window_start
                if elapsed >= 1.0:
                    self._inference_fps = self._inference_fps_window_count / elapsed
                    self._inference_fps_window_count = 0
                    self._inference_fps_window_start = time.perf_counter()

                if frame.frame_number % 30 == 0:
                    logger.info(
                        f"[FRAME FLOW] Camera '{self.camera_id}' Frame {frame.frame_number}: "
                        f"{len(res.detections)} detections, {len(res.tracks)} tracks, "
                        f"latency={self._last_inference_ms:.1f}ms, inference_fps={self._inference_fps:.1f}"
                    )

                current_tracks = res.tracks
                if current_tracks:
                    self._last_activity_time = time.perf_counter()
                elif (time.perf_counter() - self._last_activity_time) >= self._no_activity_alert_interval:
                    logger.debug(
                        f"[WATCHDOG] Camera '{self.camera_id}' perimeter clear: zero activity for "
                        f"{self._no_activity_alert_interval:.0f}s"
                    )
                    self._last_activity_time = time.perf_counter()

                if res.zone_events or res.alert_events:
                    # Guarantee evidence snapshots for every alert before persistence & broadcast
                    if res.alert_events:
                        for a in res.alert_events:
                            if not getattr(a, "evidence_snapshot_uri", None):
                                self.pipeline._attach_alert_evidence([a], frame, current_tracks)
                    evs = list(res.zone_events) + list(res.alert_events)
                    asyncio.create_task(self._safe_record_events(evs))

                # --- RENDER (synchronized with current frame perception) ---
                render_start = time.perf_counter()
                jpeg = await asyncio.to_thread(self._render, frame.image, current_tracks)
                self._last_render_ms = (time.perf_counter() - render_start) * 1000.0

                if jpeg:
                    self._last_jpeg = jpeg
                    self._publish(jpeg, frame.frame_number, len(current_tracks))
                    self._tick_fps()

                # Update pipeline stride controller overhead
                self.pipeline.set_frame_overhead_ms(self._last_read_ms + self._last_render_ms)

                #region debug-point: WORKERS heartbeat every ~1 second
                hb_now = time.perf_counter()
                if hb_now - self._workers_heartbeat_last >= 1.0:
                    rec = self.manager.get_camera(self.camera_id)
                    adapter = rec.adapter if rec else None
                    info = adapter.get_stream_info() if hasattr(adapter, "get_stream_info") else {}
                    total_frames = int(info.get("total_frames", 0) or 0)
                    current_frame = int(info.get("current_frame", 0) or 0)
                    progress_pct = (current_frame / total_frames * 100.0) if total_frames > 0 else 0.0
                    is_running = bool(getattr(adapter, "is_running", False) if adapter else False)
                    is_eof = bool(info.get("is_eof", False))
                    fps_eff = float(info.get("fps", 30.0) or 30.0)
                    media_ts = current_frame / fps_eff if fps_eff > 0 else 0.0
                    queue_size = 0
                    try:
                        from backend.ingestion.frame_buffer import get_frame_buffer_manager
                        buf = get_frame_buffer_manager().get_buffer(self.camera_id)
                        queue_size = buf.size() if buf is not None else 0
                    except Exception:
                        pass
                    logger.info(
                        f"[WORKERS] {self.camera_id} ingestion_alive={is_running and not is_eof} "
                        f"camera_worker_alive={self.is_running} "
                        f"frame={current_frame}/{total_frames} media_ts={media_ts:.2f}s "
                        f"progress={progress_pct:.1f}% queue_size={queue_size} "
                        f"display_fps={self._display_fps:.1f} inference_fps={self._inference_fps:.1f} "
                        f"read_ms={self._last_read_ms:.1f} inference_ms={self._last_inference_ms:.1f} "
                        f"encode_ms={self._last_render_ms:.1f} eof={is_eof} loop={bool(info.get('loop', False))}"
                    )
                    self._workers_heartbeat_last = hb_now
                #endregion

                # --- Pacing: throttle to source FPS for LIVE / LOOPING sources only. ---
                # Finite VIDEO_FILE (loop=False) runs as fast as possible so a
                # 5-min clip does not literally take 5 minutes to ingest.
                if enable_pacing:
                    next_deadline += frame_interval
                    now = time.perf_counter()
                    if now < next_deadline:
                        sleep_duration = next_deadline - now
                        if sleep_duration > 0.002:
                            await asyncio.sleep(sleep_duration)
                        else:
                            await asyncio.sleep(0)
                    else:
                        if now - next_deadline > frame_interval * 2:
                            next_deadline = now
                        await asyncio.sleep(0)
                else:
                    # Finite video: yield to event loop but do NOT throttle.
                    # Frame reading + inference + render is already compute-bound;
                    # a bare yield lets other async tasks (WS/MJPEG, DB writes)
                    # run between frames.
                    await asyncio.sleep(0)

        except asyncio.CancelledError:
            raise
        except Exception as err:  # pragma: no cover - defensive
            self._last_error = str(err)
            logger.exception(f"Perception worker for '{self.camera_id}' crashed: {err}")
            rec = self.manager.get_camera(self.camera_id)
            if rec is not None:
                rec.status = CameraStatus.ERROR
                rec.last_error = str(err)


class WorkerRegistry:
    """Process-wide registry of per-camera perception workers."""

    def __init__(self) -> None:
        self._workers: Dict[str, CameraWorker] = {}
        self._lock = asyncio.Lock()

    async def start_worker(self, camera_id: str) -> CameraWorker:
        """Start (or return the already-running) worker for a camera."""
        clean_id = str(camera_id).strip()
        async with self._lock:
            worker = self._workers.get(clean_id)
            if worker is not None and worker.is_running:
                return worker
            worker = await asyncio.to_thread(CameraWorker, camera_id=clean_id)
            self._workers[clean_id] = worker
        await worker.start()
        return worker

    async def stop_worker(self, camera_id: str) -> bool:
        clean_id = str(camera_id).strip()
        async with self._lock:
            worker = self._workers.pop(clean_id, None)
        if worker is None:
            return False
        await worker.stop()
        return True

    def get_worker(self, camera_id: str) -> Optional[CameraWorker]:
        return self._workers.get(str(camera_id).strip())

    def active_workers(self) -> Dict[str, CameraWorker]:
        return dict(self._workers)

    def pause_worker(self, camera_id: str) -> bool:
        worker = self._workers.get(str(camera_id).strip())
        if worker:
            worker.pause()
            return True
        return False

    def resume_worker(self, camera_id: str) -> bool:
        worker = self._workers.get(str(camera_id).strip())
        if worker:
            worker.resume()
            return True
        return False

    def is_worker_paused(self, camera_id: str) -> bool:
        worker = self._workers.get(str(camera_id).strip())
        return bool(worker.is_paused) if worker else False

    def reset_all_zone_states(self) -> None:
        """Reset in-memory zone monitor track states and evidence cooldown caches for all workers."""
        for worker in list(self._workers.values()):
            if hasattr(worker, "zone_monitor") and worker.zone_monitor:
                worker.zone_monitor.reset()
            if hasattr(worker, "pipeline") and worker.pipeline:
                if hasattr(worker.pipeline, "_evidence_last_frame"):
                    worker.pipeline._evidence_last_frame.clear()
                if hasattr(worker.pipeline, "_evidence_cache"):
                    worker.pipeline._evidence_cache.clear()

    def aggregate_metrics(self) -> Dict[str, Any]:
        """Fleet-wide totals derived from real per-worker telemetry."""
        workers = list(self._workers.values())
        running = [w for w in workers if w.is_running]
        if not running:
            return {
                "workers": len(workers),
                "workers_running": 0,
                "active_tracks": 0,
                "display_fps": 0.0,
                "ai_processing_fps": 0.0,
            }

        per_worker = [w.get_metrics() for w in running]
        return {
            "workers": len(workers),
            "workers_running": len(running),
            "active_tracks": sum(int(m.get("active_tracks", 0)) for m in per_worker),
            "display_fps": round(
                sum(float(m.get("display_fps", 0.0)) for m in per_worker) / len(per_worker), 2
            ),
            "ai_processing_fps": round(
                sum(float(m.get("ai_processing_fps", 0.0)) for m in per_worker) / len(per_worker), 2
            ),
            "inference_latency_ms": round(
                sum(float(m.get("inference_latency_ms", 0.0)) for m in per_worker) / len(per_worker), 2
            ),
            "tracking_latency_ms": round(
                sum(float(m.get("tracking_latency_ms", 0.0)) for m in per_worker) / len(per_worker), 2
            ),
            "persistence_latency_ms": round(
                sum(float(m.get("persistence_latency_ms", 0.0)) for m in per_worker) / len(per_worker), 2
            ),
            "prediction_latency_ms": round(
                sum(float(m.get("prediction_latency_ms", 0.0)) for m in per_worker) / len(per_worker), 2
            ),
            "encoding_latency_ms": round(
                sum(float(m.get("encoding_latency_ms", 0.0)) for m in per_worker) / len(per_worker), 2
            ),
            "read_latency_ms": round(
                sum(float(m.get("read_latency_ms", 0.0)) for m in per_worker) / len(per_worker), 2
            ),
            "total_pipeline_latency_ms": round(
                sum(float(m.get("total_pipeline_latency_ms", 0.0)) for m in per_worker) / len(per_worker), 2
            ),
            "total_detections": sum(int(m.get("total_detections", 0)) for m in per_worker),
            "total_alerts": sum(int(m.get("total_alerts", 0)) for m in per_worker),
            "frames_processed": sum(int(m.get("frames_processed", 0)) for m in per_worker),
            "skipped_frames": sum(int(m.get("skipped_frames", 0)) for m in per_worker),
            "predicted_frames": sum(int(m.get("predicted_frames", 0)) for m in per_worker),
            "device": per_worker[0].get("device", "cpu"),
            "frame_stride": per_worker[0].get("frame_stride", 1),
        }

    async def stop_all(self) -> None:
        async with self._lock:
            workers = list(self._workers.values())
            self._workers.clear()
        for worker in workers:
            await worker.stop()


global_worker_registry = WorkerRegistry()


def get_worker_registry() -> WorkerRegistry:
    return global_worker_registry
