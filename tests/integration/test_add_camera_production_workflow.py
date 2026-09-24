"""
Integration test for the production Add Camera flow.
Verifies GET /api/cameras/sources/available and POST /api/cameras/register
using the lightweight curated demo clips.
"""
import pytest
from httpx import ASGITransport, AsyncClient

from backend.database import init_db
from backend.main import create_app


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()


@pytest.mark.asyncio
async def test_add_camera_production_workflow():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Fetch available video sources
        r_sources = await client.get("/api/cameras/sources/available")
        assert r_sources.status_code == 200, f"Expected 200, got {r_sources.status_code}: {r_sources.text}"
        data = r_sources.json()
        assert "bundled_clips" in data
        assert len(data["bundled_clips"]) > 0

        # Check for our curated demo media
        paths = [c["path"] for c in data["bundled_clips"]]
        has_demo_clip = any("cam01" in p or "border" in p or "virat" in p for p in paths)
        assert has_demo_clip, f"None of the demo clips found in {paths}"

        # 2. Register a new camera using the curated demo clip
        selected_clip = paths[0]
        payload = {
            "camera_id": "CAM-PROD-TEST",
            "name": "Northern Sector Alpha",
            "source_type": "video_file",
            "source_url": selected_clip,
            "location_label": "Sector 9 Border Outpost",
            "loop": True,
            "autostart": False,
        }
        r_reg = await client.post("/api/cameras/register", json=payload)
        assert r_reg.status_code == 200, f"Registration failed: {r_reg.text}"
        reg_data = r_reg.json()
        assert reg_data["camera_id"] == "CAM-PROD-TEST"
        assert reg_data["location_label"] == "Sector 9 Border Outpost"

        # 3. Retrieve camera by ID
        r_get = await client.get("/api/cameras/CAM-PROD-TEST")
        assert r_get.status_code == 200
        assert r_get.json()["name"] == "Northern Sector Alpha"

        # Cleanup
        await client.delete("/api/cameras/CAM-PROD-TEST")
