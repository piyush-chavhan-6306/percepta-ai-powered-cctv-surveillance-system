"""
Border Intelligence Video File Adapter.
Implements SensorAdapter for reading MP4/AVI/MOV/MKV/WebM video files via OpenCV, with FPS throttling,
looping, and integration with the in-memory FrameBuffer.
"""
import asyncio
from datetime import datetime, timezone
import logging
import math
from pathlib import Path
import threading
from typing import Any, Dict, Optional
import cv2
import numpy as np

from backend.events.schema import SourceType
from backend.ingestion.adapter import FrameData, SensorAdapter
from backend.ingestion.frame_buffer import FrameBuffer, get_frame_buffer_manager

logger = logging.getLogger(__name__)


class VideoFileAdapter(SensorAdapter):
    """
    OpenCV-based video ingestion adapter for local surveillance video files.
    Features threaded initialization, zero-wait first-frame priming, robust metadata fallbacks,
    and reliable EOF/loop lifecycle handling.

    NOTE on CAP_PROP_FRAME_COUNT reliability:
        OpenCV's `cv2.CAP_PROP_FRAME_COUNT` is codec-dependent and OFTEN INACCURATE
        (inflated 2-25x for some VFR/H.264/AVI clips). We treat it as a *hint* for
        progress display, then ON CLEAN EOF we overwrite it with the actual counted
        frames. This eliminates the classic "progress stuck at 4%" symptom where
        `reported_total = 25 * actual_frames`.
    """

    def __init__(
        self,
        camera_id: str,
        video_path: str,
        loop: bool = False,
        target_fps: Optional[float] = None,
        frame_buffer: Optional[FrameBuffer] = None,
        modality: str = "STANDARD",
    ) -> None:
        super().__init__(camera_id=camera_id, source=SourceType.VIDEO_FILE, modality=modality)
        self.video_path = video_path
        self.loop = loop
        self.target_fps = target_fps
        self._buffer = frame_buffer or get_frame_buffer_manager().get_buffer(camera_id)

        self._cap: Optional[cv2.VideoCapture] = None
        self._read_lock = threading.Lock()
        self._frame_count = 0
        self._width = 0
        self._height = 0
        self._native_fps = 30.0
        self._total_frames_reported = 0
        self._total_frames_actual = 0
        self._primed_frame: Optional[np.ndarray] = None
        self._eof_reached = False

        self._fourcc_str = "unknown"
        self._duration_sec = 0.0

    def _open_capture_sync(self, path: Path) -> None:
        """Synchronous capture open and first-frame verification executed in worker thread."""
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise ValueError(f"Failed to open video file (unsupported format or corrupted): {path}")

        # Probe first frame to verify decodability and get exact dimensions
        ret, first_frame = cap.read()
        if not ret or first_frame is None:
            cap.release()
            raise ValueError(f"Failed to open video file (stream unreadable or empty): {path}")

        # Robust FPS detection with safe fallbacks
        fps_val = cap.get(cv2.CAP_PROP_FPS)
        if fps_val is None or math.isnan(fps_val) or fps_val <= 0.0 or fps_val > 240.0:
            self._native_fps = 30.0
        else:
            self._native_fps = float(fps_val)

        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        if w <= 0 or h <= 0:
            h, w = first_frame.shape[:2]
        self._width = w
        self._height = h

        total = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        if total is not None and not math.isnan(total) and total > 0:
            reported_total = int(total)
        else:
            reported_total = 0
        self._total_frames_reported = reported_total
        self._total_frames_actual = 0

        # Extract fourcc codec string if available
        try:
            fourcc_int = int(cap.get(cv2.CAP_PROP_FOURCC) or 0)
            if fourcc_int > 0:
                self._fourcc_str = "".join([chr((fourcc_int >> 8 * i) & 0xFF) for i in range(4)]).strip()
            else:
                self._fourcc_str = "avc1"
        except Exception:
            self._fourcc_str = "unknown"

        if self._native_fps > 0 and self._total_frames_reported > 0:
            self._duration_sec = round(self._total_frames_reported / self._native_fps, 2)
        else:
            self._duration_sec = 0.0

        self._cap = cap
        self._primed_frame = first_frame
        self._frame_count = 0
        self._eof_reached = False
        self._is_running = True

    async def start(self) -> None:
        """Open the video capture stream and validate file readability asynchronously."""
        path = Path(self.video_path)
        if not path.exists():
            raise FileNotFoundError(f"Video file not found: {self.video_path}")

        await asyncio.to_thread(self._open_capture_sync, path)
        logger.info(
            f"VideoFileAdapter started for {self.camera_id}: "
            f"{self._width}x{self._height} @ {self._native_fps} FPS [codec: {self._fourcc_str}, duration: {self._duration_sec}s] "
            f"(total frames reported={self._total_frames_reported}, loop: {self.loop})"
        )

    def read_frame_blocking(self) -> Optional[FrameData]:
        """
        Synchronous frame read. Consumes the primed first frame or reads next frame from capture.
        Dispatched via worker thread by CameraManager.
        """
        with self._read_lock:
            if not self._is_running or self._cap is None:
                return None

            if self._primed_frame is not None:
                frame = self._primed_frame
                self._primed_frame = None
                ret = True
            else:
                ret, frame = self._cap.read()
                if not ret or frame is None:
                    if self.loop:
                        self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ret, frame = self._cap.read()
                        if not ret or frame is None:
                            self._is_running = False
                            self._eof_reached = True
                            self._total_frames_actual = max(self._total_frames_actual, self._frame_count)
                            logger.warning(
                                f"[VIDEO EOF LOOP-FAIL] {self.camera_id}: loop seek failed after ret=False at frame={self._frame_count}"
                            )
                            return None
                        logger.info(
                            f"[VIDEO LOOP] {self.camera_id}: rewound from frame={self._frame_count} to start (loop=True)"
                        )
                    else:
                        self._is_running = False
                        self._eof_reached = True
                        self._total_frames_actual = max(self._total_frames_actual, self._frame_count)
                        effective_total = self._effective_total_frames()
                        logger.info(
                            f"[VIDEO EOF] {self.camera_id}: clean EOF at frame={self._frame_count}/{effective_total} "
                            f"(reported={self._total_frames_reported}, actual={self._total_frames_actual}), ret=False"
                        )
                        return None

            self._frame_count += 1
            now = datetime.now(timezone.utc)

            frame_data = FrameData(
                camera_id=self.camera_id,
                frame_number=self._frame_count,
                timestamp=now,
                image=frame,
                width=self._width,
                height=self._height,
                fps=self.target_fps or self._native_fps,
                source=self.source,
            )

            # Push to ring buffer automatically
            self._buffer.push(frame_data)

            #region debug-point: VIDEO heartbeat every 30 frames
            if self._frame_count == 1 or self._frame_count % 30 == 0:
                fps_eff = self.target_fps or self._native_fps
                media_ts = self._frame_count / fps_eff if fps_eff > 0 else 0.0
                effective_total = self._effective_total_frames()
                progress_pct = (self._frame_count / effective_total * 100.0) if effective_total > 0 else 0.0
                buffer_size = self._buffer.size() if self._buffer is not None else 0
                logger.info(
                    f"[VIDEO] {self.camera_id} frame={self._frame_count}/{effective_total} "
                    f"media_ts={media_ts:.2f}s progress={progress_pct:.1f}% "
                    f"cap_pos_frame={self._cap.get(cv2.CAP_PROP_POS_FRAMES):.0f} "
                    f"cap_pos_msec={self._cap.get(cv2.CAP_PROP_POS_MSEC):.0f}ms "
                    f"ret={ret} buffer_size={buffer_size}"
                )
            #endregion

            return frame_data

    async def get_next_frame(self) -> Optional[FrameData]:
        """Read next frame asynchronously."""
        return self.read_frame_blocking()

    def _effective_total_frames(self) -> int:
        """
        Return the best available total frame count.

        After clean EOF, CAP_PROP_FRAME_COUNT is known to be inflated for some
        codecs, so we use the *actual* counted frames. Before EOF we fall back
        to the reported value as an estimate, which is still useful for progress
        bar scaling. We also clamp reported >= actual mid-stream so a 25x
        inflation cannot keep progress pinned at 4% indefinitely: once we've
        read more than the reported count (impossible unless reported was
        wrong), we switch to `frame_count * 1.05` as a running estimate.
        """
        reported = int(self._total_frames_reported or 0)
        actual = int(self._total_frames_actual or 0)
        current = int(self._frame_count or 0)

        if self._eof_reached and actual > 0:
            return actual

        if reported > 0 and current > reported:
            return max(current, int(current * 1.05) + 1)

        if reported > 0:
            return reported

        return max(current, int(current * 1.05) + 1)

    async def stop(self) -> None:
        """Release OpenCV capture and reset state cleanly."""
        self._is_running = False
        with self._read_lock:
            self._primed_frame = None
            if self._cap is not None:
                self._cap.release()
                self._cap = None
        logger.info(f"VideoFileAdapter stopped for {self.camera_id}")

    def get_stream_info(self) -> Dict[str, Any]:
        """Return video stream metadata."""
        effective_total = self._effective_total_frames()
        return {
            "camera_id": self.camera_id,
            "source_type": self.source.value,
            "video_path": self.video_path,
            "is_running": self._is_running,
            "resolution": f"{self._width}x{self._height}",
            "width": self._width,
            "height": self._height,
            "fps": self.target_fps or self._native_fps,
            "native_fps": self._native_fps,
            "current_frame": self._frame_count,
            "total_frames": effective_total,
            "reported_total_frames": self._total_frames_reported,
            "actual_total_frames": self._total_frames_actual,
            "loop": self.loop,
            "is_eof": self._eof_reached,
            "codec": self._fourcc_str,
            "duration_sec": self._duration_sec,
        }
