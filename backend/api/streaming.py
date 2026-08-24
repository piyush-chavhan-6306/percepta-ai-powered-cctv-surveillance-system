"""
Border Intelligence Real-Time Streaming Module.
Provides:
1. WebSocket (/ws/events & /api/ws/events): Live event and alert broadcast from EventBus to web clients with JWT validation.
2. MJPEG Video Stream (/api/stream/video/{camera_id}): HTTP multipart streaming for frontend video display.
"""
import asyncio
import logging
from typing import Optional, Set
import cv2
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse

from backend.events.bus import get_event_bus
from backend.events.schema import BaseEvent
from backend.gateway.dependencies import validate_ws_token
from backend.ingestion.camera_manager import get_camera_manager

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


async def _mjpeg_generator(camera_id: str):
    """Generator yielding multipart MJPEG frames from a registered camera."""
    manager = get_camera_manager()
    last_frame_num = -1
    last_jpeg_bytes = None

    while True:
        rec = manager.get_camera(camera_id)
        if not rec or not rec.adapter.is_running:
            break

        frame_data = await manager.get_latest_frame(camera_id)
        if frame_data is not None and frame_data.image is not None:
            # Re-encode only when a fresh frame arrives
            if frame_data.frame_number != last_frame_num or last_jpeg_bytes is None:
                ret, jpeg = cv2.imencode(".jpg", frame_data.image, [cv2.IMWRITE_JPEG_QUALITY, 75])
                if ret:
                    last_jpeg_bytes = jpeg.tobytes()
                    last_frame_num = frame_data.frame_number

            if last_jpeg_bytes is not None:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + last_jpeg_bytes + b"\r\n"
                )
        else:
            await asyncio.sleep(0.02)

        await asyncio.sleep(0.008)


@router.get("/api/stream/video/{camera_id}")
async def stream_video(camera_id: str):
    """
    MJPEG video streaming endpoint for real-time browser canvas / img tag display.
    Streams multipart/x-mixed-replace format.
    """
    manager = get_camera_manager()
    cam = manager.get_camera(camera_id)
    if not cam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera '{camera_id}' not found in registry",
        )

    return StreamingResponse(
        _mjpeg_generator(camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
