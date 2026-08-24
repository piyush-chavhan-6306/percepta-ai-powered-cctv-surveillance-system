"""
Border Intelligence Video File Adapter.
Implements SensorAdapter for reading MP4/AVI video files via OpenCV, with FPS throttling,
looping, and integration with the in-memory FrameBuffer.
"""
from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Any, Dict, Optional
import cv2

from backend.events.schema import SourceType
from backend.ingestion.adapter import FrameData, SensorAdapter
from backend.ingestion.frame_buffer import FrameBuffer, get_frame_buffer_manager

logger = logging.getLogger(__name__)


class VideoFileAdapter(SensorAdapter):
    """
    OpenCV-based video ingestion adapter for local surveillance video files.
    """

    def __init__(
        self,
        camera_id: str,
        video_path: str,
        loop: bool = False,
        target_fps: Optional[float] = None,
        frame_buffer: Optional[FrameBuffer] = None,
    ) -> None:
        super().__init__(camera_id=camera_id, source=SourceType.VIDEO_FILE)
        self.video_path = video_path
        self.loop = loop
        self.target_fps = target_fps
        self._buffer = frame_buffer or get_frame_buffer_manager().get_buffer(camera_id)

        self._cap: Optional[cv2.VideoCapture] = None
        self._frame_count = 0
        self._width = 0
        self._height = 0
        self._native_fps = 30.0
        self._total_frames = 0

    async def start(self) -> None:
        """Open the video capture stream and validate file readability."""
        path = Path(self.video_path)
        if not path.exists():
            raise FileNotFoundError(f"Video file not found: {self.video_path}")

        self._cap = cv2.VideoCapture(str(path))

        if not self._cap.isOpened():
            raise ValueError(f"Failed to open video file (unsupported format or corrupted): {self.video_path}")

        self._width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self._height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self._native_fps = float(self._cap.get(cv2.CAP_PROP_FPS) or 30.0)
        self._total_frames = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self._frame_count = 0
        self._is_running = True
        logger.info(f"VideoFileAdapter started for {self.camera_id}: {self._width}x{self._height} @ {self._native_fps} FPS")

    async def get_next_frame(self) -> Optional[FrameData]:
        """
        Read the next frame from the video stream.
        Automatically handles looping or stream termination.
        """
        if not self._is_running or self._cap is None:
            return None

        ret, frame = self._cap.read()

        if not ret or frame is None:
            if self.loop:
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self._cap.read()
                if not ret or frame is None:
                    self._is_running = False
                    return None
            else:
                self._is_running = False
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
        return frame_data

    async def stop(self) -> None:
        """Release OpenCV capture and reset state."""
        self._is_running = False
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        logger.info(f"VideoFileAdapter stopped for {self.camera_id}")

    def get_stream_info(self) -> Dict[str, Any]:
        """Return video stream metadata."""
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
            "total_frames": self._total_frames,
            "loop": self.loop,
        }
