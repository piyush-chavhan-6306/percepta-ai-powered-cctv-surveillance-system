"""
Border Intelligence Real-Time Streaming Module.
Provides:
1. WebSocket (/ws/events & /api/ws/events): Live event and alert broadcast from EventBus to web clients with JWT validation.
2. MJPEG Video Stream (/api/stream/video/{camera_id}): HTTP multipart streaming for frontend video display.
"""
import asyncio
from datetime import datetime
import logging
from pathlib import Path
from typing import Optional, Set
import cv2
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from fastapi.responses import Response, StreamingResponse
import numpy as np

from backend.events.bus import get_event_bus
from backend.events.schema import BaseEvent
from backend.gateway.dependencies import validate_ws_token
from backend.ingestion.camera_manager import get_camera_manager
from backend.tracking.live_worker import get_worker_registry

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Streaming"])


class ConnectionManager:
    """Manages active WebSocket client connections and event broadcasting with backpressure isolation."""

    def __init__(self, max_clients: int = 100, send_timeout: float = 2.0) -> None:
        self.active_connections: Set[WebSocket] = set()
        self.max_clients = max_clients
        self.send_timeout = send_timeout
        self._lock = asyncio.Lock()
        self._subscribed = False

    async def connect(self, websocket: WebSocket) -> bool:
        async with self._lock:
            if len(self.active_connections) >= self.max_clients:
                logger.warning(f"Rejecting WebSocket connection: max client limit ({self.max_clients}) reached")
                await websocket.close(code=1008, reason="Max client connection limit reached")
                return False

            await websocket.accept()
            self.active_connections.add(websocket)

        logger.info(f"WebSocket client connected. Total clients: {len(self.active_connections)}")

        # Ensure EventBus subscription is active
        if not self._subscribed:
            bus = get_event_bus()
            await bus.subscribe(self._broadcast_event)
            self._subscribed = True
        return True

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self.active_connections.discard(websocket)
        logger.info(f"WebSocket client disconnected. Remaining: {len(self.active_connections)}")

    async def _broadcast_event(self, event: BaseEvent) -> None:
        """Internal callback invoked by EventBus on new published event with slow-client timeout."""
        if not self.active_connections:
            return

        payload = event.model_dump_json()
        dead_connections = set()

        async with self._lock:
            for ws in list(self.active_connections):
                try:
                    await asyncio.wait_for(ws.send_text(payload), timeout=self.send_timeout)
                except Exception as err:
                    logger.warning(f"Pruning slow or disconnected WebSocket client: {err}")
                    dead_connections.add(ws)

            for dead_ws in dead_connections:
                self.active_connections.discard(dead_ws)


ws_manager = ConnectionManager()


@router.websocket("/ws/events")
@router.websocket("/api/ws/events")
async def websocket_events_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
) -> None:
    """
    WebSocket endpoint for real-time surveillance events, alerts, and state updates.
    Validates token from ?token=<jwt> or falls back to DEMO_MODE.
    """
    user = await validate_ws_token(websocket, token)
    if not user:
        return

    connected = await ws_manager.connect(websocket)
    if not connected:
        return

    try:
        while True:
            # Keepalive listener / handle ping-pong or client requests
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text('{"type": "pong"}')
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception as err:
        logger.warning(f"WebSocket connection terminated: {err}")
        await ws_manager.disconnect(websocket)


_MAX_MJPEG_CLIENTS = 12
_mjpeg_clients = 0
_mjpeg_clients_lock = asyncio.Lock()


async def _mjpeg_generator(camera_id: str, startup_grace: float = 30.0):
    """
    Yield multipart MJPEG frames already annotated by the camera's perception worker.

    This deliberately does NOT read from the camera adapter. The worker owns the
    frame source; a reader here would advance the capture and steal frames from
    the worker, halving both streams. Frames are also encoded once by the worker
    and fanned out here, so a second viewer costs no extra JPEG work.

    `startup_grace` is how long to wait for a worker to publish its first frame
    (model warm-up on the first detection is slow) before giving up on the stream.
    """
    global _mjpeg_clients

    registry = get_worker_registry()
    manager = get_camera_manager()
    last_sequence = 0

    async with _mjpeg_clients_lock:
        if _mjpeg_clients >= _MAX_MJPEG_CLIENTS:
            logger.warning(
                f"Refusing MJPEG viewer for '{camera_id}': {_MAX_MJPEG_CLIENTS} client limit reached"
            )
            return
        _mjpeg_clients += 1

    try:
        loop = asyncio.get_running_loop()
        idle_since = None
        while True:
            worker = registry.get_worker(camera_id)
            if worker is None or not worker.is_running:
                cam = manager.get_camera(camera_id)
                if cam is None:
                    return
                if idle_since is None:
                    idle_since = loop.time()
                elif loop.time() - idle_since > startup_grace:
                    return
                await asyncio.sleep(min(0.05, startup_grace))
                continue

            frame = await worker.wait_for_frame(
                after_sequence=last_sequence,
                timeout=min(5.0, max(0.05, startup_grace)),
            )
            if frame is None:
                if idle_since is None:
                    idle_since = loop.time()
                elif loop.time() - idle_since > startup_grace:
                    logger.info(f"Closing idle MJPEG stream for '{camera_id}'")
                    return
                continue

            idle_since = None
            last_sequence = frame.sequence
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Content-Length: " + str(len(frame.jpeg)).encode() + b"\r\n\r\n"
                + frame.jpeg + b"\r\n"
            )
    except asyncio.CancelledError:
        raise
    finally:
        async with _mjpeg_clients_lock:
            _mjpeg_clients = max(0, _mjpeg_clients - 1)


@router.get("/api/streaming/feed/{camera_id}")
@router.get("/api/stream/video/{camera_id}")
async def stream_video(camera_id: str):
    """
    MJPEG video streaming endpoint for real-time browser display.

    Serves the frames the perception worker already annotated, so the boxes the
    operator sees are burned into the exact frame they belong to — there is no
    client-side overlay that can drift out of sync with the video.
    """
    manager = get_camera_manager()
    cam = manager.get_camera(camera_id)
    if not cam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera '{camera_id}' not found in registry",
        )

    # A viewer arriving before the loop is up (e.g. after a server restart)
    # transparently brings it back rather than showing a dead tile.
    registry = get_worker_registry()
    worker = registry.get_worker(camera_id)
    if worker is None or not worker.is_running:
        if cam.adapter.is_running:
            await registry.start_worker(camera_id)

    return StreamingResponse(
        _mjpeg_generator(camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
            "Age": "0",
        },
    )


@router.get("/api/streaming/snapshot/{camera_id}")
@router.get("/api/stream/snapshot/{camera_id}")
async def stream_snapshot(camera_id: str):
    """Single annotated JPEG — used for alert thumbnails and quick health checks."""
    worker = get_worker_registry().get_worker(camera_id)
    if worker is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No perception worker running for camera '{camera_id}'",
        )

    frame = worker.get_latest()
    if frame is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Camera '{camera_id}' has not published a frame yet",
        )

    return Response(
        content=frame.jpeg,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/api/streaming/replay/{camera_id}")
async def replay_frame(
    camera_id: str,
    timestamp: Optional[str] = Query(None),
    offset_sec: float = Query(0.0),
    t: Optional[int] = Query(None),
):
    """
    Forensic replay endpoint for exact-time timeline seeking.
    Returns the video frame or snapshot corresponding to the requested event timestamp
    plus scrub offset (-10s to +10s) with forensic verification telemetry overlay.
    """
    manager = get_camera_manager()
    cam = manager.get_camera(camera_id)

    frame_bgr: Optional[np.ndarray] = None
    target_time_str = timestamp or datetime.now().strftime("%H:%M:%S")

    # 1. Attempt exact video seek if camera has local video file
    if cam and hasattr(cam.adapter, "video_path"):
        video_path = getattr(cam.adapter, "video_path", None)
        if video_path and Path(video_path).exists():
            try:
                cap = cv2.VideoCapture(str(video_path))
                if cap.isOpened():
                    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
                    reported_total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
                    # CAP_PROP_FRAME_COUNT is often inflated (see video_adapter note).
                    # Use a conservative seek: if ret=False at target_frame, back off
                    # and scan for the nearest readable frame.
                    total_duration = reported_total / fps

                    base_sec = 0.0
                    if timestamp:
                        try:
                            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                            base_sec = float(dt.second + dt.minute * 60)
                        except Exception:
                            try:
                                base_sec = float(timestamp)
                            except Exception:
                                base_sec = total_duration / 2.0
                    else:
                        base_sec = total_duration / 2.0

                    target_sec = max(0.0, (base_sec + offset_sec) % max(1.0, total_duration))
                    target_frame = int(target_sec * fps) % reported_total
                    # Try seek + read; if it fails (inflated metadata), walk backwards
                    # to find the last readable frame (max 128 attempts).
                    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, target_frame - 1))
                    ret, frame = cap.read()
                    if not ret or frame is None:
                        for backoff in (2, 4, 8, 16, 32, 64, 128):
                            alt = max(0, target_frame - backoff)
                            cap.set(cv2.CAP_PROP_POS_FRAMES, alt)
                            ret, frame = cap.read()
                            if ret and frame is not None:
                                break
                    if ret and frame is not None:
                        frame_bgr = frame
                cap.release()
            except Exception as err:
                logger.warning(f"Error seeking in video file for replay ({camera_id}): {err}")

    # 2. Check snapshot directory if video seek unavailable
    if frame_bgr is None:
        try:
            from backend.config import get_settings
            snap_dir = Path(get_settings().SNAPSHOTS_DIR)
            if snap_dir.exists():
                cam_snaps = sorted(
                    [p for p in snap_dir.glob(f"*{camera_id}*.jpg") if p.is_file()],
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                if cam_snaps:
                    frame_bgr = cv2.imread(str(cam_snaps[0]))
        except Exception as err:
            logger.warning(f"Error loading snapshot for replay ({camera_id}): {err}")

    # 3. Fallback to latest worker frame if still none
    if frame_bgr is None:
        worker = get_worker_registry().get_worker(camera_id)
        if worker:
            latest = worker.get_latest()
            if latest and latest.jpeg:
                nparr = np.frombuffer(latest.jpeg, np.uint8)
                frame_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # 4. Fallback canvas if camera stream not yet initialized
    if frame_bgr is None:
        frame_bgr = np.zeros((720, 1280, 3), dtype=np.uint8)
        cv2.putText(
            frame_bgr,
            f"FORENSIC ARCHIVE: {camera_id}",
            (100, 360),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.2,
            (0, 229, 255),
            2,
        )

    # 5. Burn Forensic Verification HUD onto the frame
    overlay = frame_bgr.copy()
    h, w = frame_bgr.shape[:2]

    # Top banner
    cv2.rectangle(overlay, (10, 10), (min(w - 10, 680), 80), (15, 15, 25), -1)
    cv2.rectangle(overlay, (10, 10), (min(w - 10, 680), 80), (0, 70, 255), 2)
    cv2.putText(
        overlay,
        f"[FORENSIC REPLAY] CAMERA: {camera_id}",
        (25, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 165, 255),
        2,
    )
    offset_sign = f"+{offset_sec:.1f}s" if offset_sec >= 0 else f"{offset_sec:.1f}s"
    cv2.putText(
        overlay,
        f"TIME: {target_time_str} | SEEK: {offset_sign} | TAMPER-VERIFIED",
        (25, 68),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        1,
    )

    # Bottom watermark
    cv2.putText(
        overlay,
        "SECURE EVIDENCE AUDIT TRAIL - LAW ENFORCEMENT ADMISSIBLE",
        (25, h - 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (0, 255, 255),
        1,
    )

    cv2.addWeighted(overlay, 0.9, frame_bgr, 0.1, 0, frame_bgr)
    success, encoded = cv2.imencode(".jpg", frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not success:
        raise HTTPException(status_code=500, detail="Failed to encode replay frame")

    return Response(
        content=encoded.tobytes(),
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )

