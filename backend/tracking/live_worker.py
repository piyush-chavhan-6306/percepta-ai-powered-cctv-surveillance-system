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
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import time
from typing import Any, Dict, List, Optional

import numpy as np

from backend.config import get_settings
from backend.ingestion.camera_manager import CameraManager, CameraStatus, get_camera_manager
from backend.tracking.overlay import annotate_frame, draw_offline, encode_jpeg
from backend.tracking.pipeline import TrackingPipeline
from backend.zones.security_zone import ZoneMonitor, get_zone_monitor

logger = logging.getLogger(__name__)

# One lock shared by every worker in the process. The YOLO model is a single
# shared instance and is not re-entrant, so concurrent cameras must serialize
# inference. On CPU they would contend anyway; this makes the contention safe.
_inference_lock = asyncio.Lock()


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
        self.jpeg_quality = jpeg_quality
        self.reconnect_max_delay = reconnect_max_delay

        # Private per-track state, shared zone/boundary definitions: a zone added
        # through /api/zones is picked up live, without cross-camera state bleed.
        self.zone_monitor: ZoneMonitor = ZoneMonitor.with_shared_definitions(get_zone_monitor())

        self.pipeline = pipeline or TrackingPipeline(
            zone_monitor=self.zone_monitor,
            frame_stride=settings.DEFAULT_FRAME_STRIDE,
            target_fps=settings.TARGET_FPS,
            min_frame_stride=settings.MIN_FRAME_STRIDE,
            max_frame_stride=settings.MAX_FRAME_STRIDE,
            adaptive_stride_enabled=settings.ADAPTIVE_STRIDE_ENABLED,
            enable_intermediate_predictions=True,
            inference_lock=_inference_lock,
        )

        self._target_fps = target_fps
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

    # ---------------------------------------------------------------- lifecycle

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
        self._task = asyncio.create_task(self._run(), name=f"perception:{self.camera_id}")
        logger.info(f"Perception worker started for camera '{self.camera_id}'")

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
        logger.info(f"Perception worker stopped for camera '{self.camera_id}'")

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
        metrics.update(
            {
                "camera_id": self.camera_id,
                "display_fps": round(self._display_fps, 2),
                "worker_running": self.is_running,
                "reconnects": self._reconnects,
                "published_frames": self._sequence,
                "last_frame_number": latest.frame_number if latest else 0,
                "jpeg_bytes": len(latest.jpeg) if latest else 0,
                "read_latency_ms": round(self._last_read_ms, 2),
                "encoding_latency_ms": round(self._last_render_ms, 2),
                "started_at": self._started_at.isoformat() if self._started_at else None,
                "last_error": self._last_error,
            }
        )
        return metrics

    # --------------------------------------------------------------- internals

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
        annotated = annotate_frame(
            image,
            tracks,
            zones=list(self.zone_monitor.zones.values()),
            boundaries=list(self.zone_monitor.boundaries.values()),
            camera_id=self.camera_id,
            display_fps=self._display_fps,
            inference_fps=metrics.get("ai_processing_fps"),
            device=str(metrics.get("device", "cpu")),
            stride=int(metrics.get("frame_stride", 1)),
            degraded=degraded,
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
        long outage does not turn into an hours-long blind spot.
        """
        self._reconnects += 1
        delay = 1.0
        attempt = 0
        await self._publish_offline_card("reconnecting…")

        while not self._stopping:
            attempt += 1
            ok = await self.manager.reconnect_camera(self.camera_id, max_retries=1, base_delay=0.0)
            if ok:
                logger.info(f"Camera '{self.camera_id}' reconnected after {attempt} attempt(s)")
                self._consecutive_read_failures = 0
                self._last_error = None
                # A new capture means new object identities; keep IDs honest.
                self.pipeline.reset()
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
        """Main perception loop. Runs until cancelled."""
        record = self.manager.get_camera(self.camera_id)
        if record is None:
            logger.error(f"Perception worker for '{self.camera_id}' aborted: camera not registered")
            return

        info = record.adapter.get_stream_info() if hasattr(record.adapter, "get_stream_info") else {}
        source_fps = self._target_fps or float(info.get("fps") or info.get("native_fps") or 25.0)
        frame_interval = 1.0 / source_fps if source_fps > 0 else 0.04
        max_read_failures = 15

        logger.info(
            f"Perception loop running for '{self.camera_id}' at up to {source_fps:.1f} fps "
            f"(stride {self.pipeline.frame_stride})"
        )

        # Deadline-based pacing. Sleeping `frame_interval - elapsed` after every
        # frame gives each frame its own floor, so a detection frame that overruns
        # the budget is never made up for and the cheap prediction frames that
        # follow are padded out to the interval instead of absorbing the overrun.
        # Tracking an absolute deadline lets a 70 ms detection frame be followed by
        # 15 ms prediction frames that catch back up, which is what keeps the
        # delivered rate near the source rate instead of well below it.
        next_deadline = time.perf_counter()

        try:
            while not self._stopping:
                cycle_start = time.perf_counter()

                frame = await self.manager.get_latest_frame(self.camera_id)
                self._last_read_ms = (time.perf_counter() - cycle_start) * 1000.0

                if frame is None or frame.image is None:
                    record = self.manager.get_camera(self.camera_id)
                    if record is None:
                        return  # deregistered underneath us
                    self._consecutive_read_failures += 1
                    source_dead = (
                        not record.adapter.is_running
                        or self._consecutive_read_failures >= max_read_failures
                    )
                    if source_dead:
                        if not await self._reconnect():
                            return
                    else:
                        await asyncio.sleep(0.05)
                    continue

                self._consecutive_read_failures = 0

                # Every frame goes through the pipeline. On stride-skipped frames
                # it costs ~0.2 ms and returns Kalman-predicted boxes, which is
                # what keeps the displayed boxes smooth between detections
                # instead of visibly stepping at the detection rate.
                result = await self.pipeline.process_frame(frame)

                render_start = time.perf_counter()
                jpeg = await asyncio.to_thread(self._render, frame.image, result.tracks)
                self._last_render_ms = (time.perf_counter() - render_start) * 1000.0
                if jpeg:
                    self._publish(jpeg, frame.frame_number, len(result.tracks))
                    self._tick_fps()

                # Let the stride controller see the full cost of a delivered frame.
                self.pipeline.set_frame_overhead_ms(self._last_read_ms + self._last_render_ms)

                # Pace to the source's real rate. Without this a video file is
                # consumed as fast as the CPU allows and plays back at 3x speed.
                next_deadline += frame_interval
                now = time.perf_counter()
                if now < next_deadline:
                    await asyncio.sleep(next_deadline - now)
                elif now - next_deadline > frame_interval * 4:
                    # Far enough behind that catching up is hopeless (a long stall,
                    # or inference slower than the source rate). Re-base instead of
                    # accumulating an ever-growing debt that would then spin the
                    # loop with zero sleep forever.
                    next_deadline = now
                    await asyncio.sleep(0)  # yield so MJPEG writes and WS sends run
                else:
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
            worker = CameraWorker(camera_id=clean_id)
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
