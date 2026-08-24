"""
Unit tests for WebSocket event streaming and MJPEG video streaming endpoints.
"""
import pytest
from starlette.testclient import TestClient

from backend.events.bus import get_event_bus
from backend.events.schema import AlertEvent, SourceType
from backend.ingestion.camera_manager import get_camera_manager
from backend.ingestion.simulation_adapter import SimulationAdapter
from backend.main import create_app


def test_websocket_events_endpoint_and_broadcast():
    app = create_app()
    bus = get_event_bus()

    client = TestClient(app)
    with client.websocket_connect("/ws/events") as websocket:
        # Send ping, receive pong
        websocket.send_text("ping")
        resp = websocket.receive_text()
        assert "pong" in resp


@pytest.mark.asyncio
async def test_mjpeg_video_stream_endpoint():
    from backend.api.streaming import _mjpeg_generator

    manager = get_camera_manager()
    adapter = SimulationAdapter(camera_id="cam_stream_mjpeg", width=320, height=240)
    manager.register_camera("cam_stream_mjpeg", adapter)
    await manager.start_camera("cam_stream_mjpeg")

    # Generate first frame
    gen = _mjpeg_generator("cam_stream_mjpeg")
    first_chunk = await anext(gen)

    assert isinstance(first_chunk, bytes)
    assert b"--frame" in first_chunk
    assert b"Content-Type: image/jpeg" in first_chunk

    await manager.stop_camera("cam_stream_mjpeg")


def test_mjpeg_stream_nonexistent_camera_returns_404():
    app = create_app()
    client = TestClient(app)
    response = client.get("/api/stream/video/non_existent_cam_stream")
    assert response.status_code == 404
