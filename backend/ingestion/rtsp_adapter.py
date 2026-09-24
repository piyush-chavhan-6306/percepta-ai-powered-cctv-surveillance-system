"""
Border Intelligence RTSP Camera Adapter.
Provides real-time RTSP/CCTV IP camera ingestion with credential sanitization,
zero-lag buffer flushing background thread, timeout protection, non-blocking frame capture,
and graceful error handling.
"""
from datetime import datetime, timezone
import logging
import re
import threading
import time
from typing import Any, Dict, Optional
import cv2
import numpy as np

from backend.events.schema import SourceType
from backend.ingestion.adapter import FrameData, SensorAdapter
from backend.ingestion.frame_buffer import FrameBuffer, get_frame_buffer_manager

logger = logging.getLogger(__name__)


def sanitize_rtsp_url(url: str) -> str:
    """Mask credentials in RTSP URL to prevent leaking passwords in logs or API responses."""
    if not url:
        return ""
    # Matches rtsp://username:password@host...
    return re.sub(r"://([^:@]+):([^@]+)@", r"://\1:***@", url)


class RTSPAdapter(SensorAdapter):
    """
    RTSP / IP Camera Ingestion Adapter.
    Connects to live RTSP/HTTP streams with timeout safety, credential protection,
    and a zero-lag background grabber thread preventing frame lag buffer buildup.
    """

    def __init__(
        self,
        camera_id: str,
        rtsp_url: str,
        target_fps: Optional[float] = None,
        frame_buffer: Optional[FrameBuffer] = None,
        connect_timeout_sec: float = 5.0,
        enable_zero_lag: bool = True,
    ) -> None:
        super().__init__(camera_id=camera_id, source=SourceType.VIDEO_FILE)
        self.rtsp_url = rtsp_url
        self.sanitized_url = sanitize_rtsp_url(rtsp_url)
        self.target_fps = target_fps
        self.connect_timeout_sec = connect_timeout_sec
        self.enable_zero_lag = enable_zero_lag
        self._buffer = frame_buffer or get_frame_buffer_manager().get_buffer(camera_id)

        self._cap: Optional[cv2.VideoCapture] = None
        self._frame_count = 0
        self._width = 1280
        self._height = 720
        self._native_fps = 30.0
        self._consecutive_failures = 0
        self._max_consecutive_failures = 10

        self._grabber_thread: Optional[threading.Thread] = None
        self._frame_lock = threading.Lock()
        self._latest_raw_frame: Optional[np.ndarray] = None
        self._new_frame_event = threading.Event()

    async def start(self) -> None:
        """Connect to RTSP stream and start background zero-lag grabber if enabled."""
        if not self.rtsp_url:
            raise ValueError(f"Empty RTSP URL provided for camera '{self.camera_id}'")

        logger.info(f"Opening RTSP stream for '{self.camera_id}' at {self.sanitized_url}")
        self._cap = cv2.VideoCapture(self.rtsp_url)

        if not self._cap.isOpened():
            raise ConnectionError(f"Failed to connect to RTSP stream: {self.sanitized_url}")

        w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if w > 0 and h > 0:
            self._width = w
            self._height = h

        fps = float(self._cap.get(cv2.CAP_PROP_FPS) or 30.0)
        if fps > 0:
            self._native_fps = fps

        self._frame_count = 0
        self._consecutive_failures = 0
        self._is_running = True

        if self.enable_zero_lag:
            self._grabber_thread = threading.Thread(
                target=self._zero_lag_grabber_loop,
                name=f"RTSP-ZeroLag-{self.camera_id}",
                daemon=True,
            )
            self._grabber_thread.start()

        logger.info(
            f"RTSP stream connected for '{self.camera_id}': {self._width}x{self._height} @ "
            f"{self._native_fps} FPS (zero_lag={self.enable_zero_lag})"
        )

    def _zero_lag_grabber_loop(self) -> None:
        """
        Background daemon thread continuously grabbing frames from RTSP stream.
        Flushes stale OpenCV OS-level buffers so inference consumers always receive
        the freshest frame (< 30ms latency).
        """
        while self._is_running and self._cap is not None and self._cap.isOpened():
            try:
                grabbed = self._cap.grab()
                if not grabbed:
                    self._consecutive_failures += 1
                    if self._consecutive_failures >= self._max_consecutive_failures:
                        logger.warning(
                            f"RTSP camera '{self.camera_id}' grab failure threshold reached ({self._consecutive_failures})"
                        )
                        self._is_running = False
                        break
                    time.sleep(0.01)
                    continue

                ret, frame = self._cap.retrieve()
                if ret and frame is not None:
                    with self._frame_lock:
                        self._latest_raw_frame = frame
                        self._consecutive_failures = 0
                    self._new_frame_event.set()
                else:
                    self._consecutive_failures += 1
            except Exception as e:
                logger.error(f"Error in zero-lag grabber for '{self.camera_id}': {e}")
                time.sleep(0.02)

            time.sleep(0.001)

    def read_frame_blocking(self) -> Optional[FrameData]:
        """
        Synchronous RTSP frame read.
        If zero_lag is enabled, fetches the most recent frame decoded by the grabber thread.
        Otherwise falls back to synchronous read.
        """
        if not self._is_running or self._cap is None:
            return None

        frame: Optional[np.ndarray] = None

        if self.enable_zero_lag:
            # Wait for next fresh frame up to connect_timeout_sec
            if self._new_frame_event.wait(timeout=self.connect_timeout_sec):
                self._new_frame_event.clear()
                with self._frame_lock:
                    if self._latest_raw_frame is not None:
                        frame = self._latest_raw_frame.copy()
            if frame is None:
                self._consecutive_failures += 1
                if self._consecutive_failures >= self._max_consecutive_failures:
                    logger.warning(f"RTSP camera '{self.camera_id}' timed out waiting for zero-lag frame")
                    self._is_running = False
                return None
        else:
            ret, frame = self._cap.read()
            if not ret or frame is None:
                self._consecutive_failures += 1
                if self._consecutive_failures >= self._max_consecutive_failures:
                    logger.warning(f"RTSP camera '{self.camera_id}' exceeded failure threshold ({self._consecutive_failures})")
                    self._is_running = False
                return None

        self._consecutive_failures = 0
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

        self._buffer.push(frame_data)
        return frame_data

    async def get_next_frame(self) -> Optional[FrameData]:
        """Fetch next frame from RTSP stream."""
        return self.read_frame_blocking()

    async def stop(self) -> None:
        """Release RTSP stream and terminate grabber thread."""
        self._is_running = False
        self._new_frame_event.set()
        if self._grabber_thread is not None and self._grabber_thread.is_alive():
            self._grabber_thread.join(timeout=1.0)
            self._grabber_thread = None
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        logger.info(f"RTSP stream stopped for '{self.camera_id}'")

    def get_stream_info(self) -> Dict[str, Any]:
        """Return RTSP stream info with sanitized URL and buffer mode."""
        return {
            "camera_id": self.camera_id,
            "source_type": "rtsp",
            "stream_url": self.sanitized_url,
            "is_running": self._is_running,
            "zero_lag_buffered": self.enable_zero_lag,
            "resolution": f"{self._width}x{self._height}",
            "width": self._width,
            "height": self._height,
            "fps": self.target_fps or self._native_fps,
            "native_fps": self._native_fps,
            "current_frame": self._frame_count,
        }
