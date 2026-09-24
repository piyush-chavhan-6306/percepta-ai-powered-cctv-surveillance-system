"""
Unit tests for Phase 24: Camera Lifecycle and safe deletion.
Verifies:
- Safe camera decommission.
- Cleaning up active incidents and alerts so no orphaned cards remain.
- Updating camera topology on camera deletion.
"""
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from backend.main import app
from backend.database import init_db
from backend.ingestion.camera_manager import get_camera_manager
from backend.incidents.service import get_incident_manager
from backend.topology.service import get_topology

from backend.ingestion.simulation_adapter import SimulationAdapter


@pytest.fixture(autouse=True)
async def ensure_db():
    await init_db()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.mark.anyio
async def test_camera_deletion_cleans_up_incidents_and_topology(client):
    cam_id = "DECOMMISSION_TEST_CAM"
    manager = get_camera_manager()
    adapter = SimulationAdapter(camera_id=cam_id, width=640, height=480)
    manager.register_camera(cam_id, adapter, name="Decommission Camera")

    # 1. Register a camera edge in topology
    topo = get_topology()
    topo.add_edge("CAM-01", cam_id, min_time_s=2.0, max_time_s=30.0)
    assert cam_id in topo.get_adjacent_cameras("CAM-01")

    # 2. Create an active incident on this camera
    inc_mgr = get_incident_manager()
    inc, alert, _ = await inc_mgr.process_event(
        event_type="perimeter_breach",
        camera_id=cam_id,
        threat_score=80.0,
        threat_level="CRITICAL",
        zone_id="TEST-ZONE",
    )
    assert inc.status in ("DETECTED", "ACTIVE", "ESCALATED")

    # 3. Call DELETE /api/cameras/{cam_id}
    resp = client.delete(f"/api/cameras/{cam_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("deregistered", "success")

    # 4. Verify topology edge was removed
    assert cam_id not in topo.get_adjacent_cameras("CAM-01")

    # 5. Verify incident was marked RESOLVED (no orphaned active incidents)
    timeline = await inc_mgr.get_incident_timeline(inc.incident_id)
    assert timeline["status"] == "RESOLVED"
