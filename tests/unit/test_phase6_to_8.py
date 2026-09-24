"""
Unit and integration tests for Phase 6 (Global Entity), Phase 7 (Cross-Camera Tracking/Re-ID),
and Phase 8 (Camera Topology).
"""

import pytest
import numpy as np
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from backend.main import app
from backend.entities.service import get_entity_manager, GlobalEntityManager
from backend.entities.models import EntityType, EntityStatus
from backend.topology.service import (
    CameraTopology,
    RelationshipType,
    get_topology,
)
from backend.tracking.reid_manager import GlobalIdentityManager, MatchDecision


@pytest.fixture(autouse=True)
async def ensure_db():
    from backend.database import init_db
    await init_db()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class TestCameraTopology:
    """Phase 8: Explicit camera relationships, timing windows, and transition plausibility."""

    def test_default_topology_seeded(self):
        topo = CameraTopology()
        dict_rep = topo.to_dict()
        assert dict_rep["total_nodes"] >= 4
        assert dict_rep["total_edges"] >= 4
        assert "CAM-01" in dict_rep["nodes"]
        assert "CAM-02" in dict_rep["nodes"]

    def test_add_and_get_edges(self):
        topo = CameraTopology()
        edge = topo.add_edge(
            from_camera="ALPHA",
            to_camera="BETA",
            relationship=RelationshipType.SEQUENTIAL,
            min_time_s=3.0,
            max_time_s=60.0,
            avg_time_s=15.0,
            bidirectional=True,
        )
        assert edge.from_camera == "ALPHA"
        assert edge.to_camera == "BETA"
        assert "BETA" in topo.get_adjacent_cameras("ALPHA")
        assert "ALPHA" in topo.get_adjacent_cameras("BETA")

    def test_transition_plausibility_same_camera(self):
        topo = CameraTopology()
        plausible, score, reason = topo.evaluate_transition_plausibility("CAM-01", "CAM-01", 10.0)
        assert plausible is True
        assert score == 1.0

    def test_transition_plausibility_valid_window(self):
        topo = CameraTopology()
        # Seeded CAM-01 -> CAM-02: min=2.0s, max=60.0s, avg=10.0s
        plausible, score, reason = topo.evaluate_transition_plausibility("CAM-01", "CAM-02", 10.0)
        assert plausible is True
        assert score >= 0.8
        assert "Plausible transition" in reason

    def test_transition_plausibility_too_rapid(self):
        topo = CameraTopology()
        # min is 2.0s, elapsed is 0.5s -> physical impossibility
        plausible, score, reason = topo.evaluate_transition_plausibility("CAM-01", "CAM-02", 0.5)
        assert plausible is False
        assert score <= 0.2
        assert "physical impossibility" in reason

    def test_transition_plausibility_unlinked_cameras(self):
        topo = CameraTopology()
        # CAM-01 has configured edges, but not to UNKNOWN-CAM-99
        plausible, score, reason = topo.evaluate_transition_plausibility("CAM-01", "UNKNOWN-CAM-99", 15.0)
        assert plausible is False
        assert score <= 0.1
        assert "No topological relationship" in reason


class TestGlobalEntityAndReID:
    """Phase 6 & 7: Global entity persistence, multi-camera Re-ID with topology gating."""

    @pytest.mark.anyio
    async def test_global_entity_manager_create_and_update(self):
        mgr = get_entity_manager()
        # Create a person entity
        res = await mgr.create_entity(
            entity_type="person",
            camera_id="CAM-01",
            local_track_id="L-101",
            meta={"clothing": "dark jacket"},
        )
        assert res.display_id.startswith("GLOBAL-PERSON-")
        assert res.entity_type == "person"
        assert res.current_camera_id == "CAM-01"
        assert res.current_local_track_id == "L-101"

        # Update entity on new camera
        res_updated = await mgr.update_entity_location(
            entity_key=res.display_id,
            camera_id="CAM-02",
            local_track_id="L-202",
        )
        assert res_updated.display_id == res.display_id
        assert res_updated.current_camera_id == "CAM-02"
        assert res_updated.current_local_track_id == "L-202"

    def test_reid_same_track_continuity(self):
        reid = GlobalIdentityManager(similarity_threshold=0.60, use_topology=False)
        vec = np.random.randn(512).astype(np.float32)
        vec = vec / np.linalg.norm(vec)

        d1 = reid.observe("CAM-01", "T-1", vec, ts=100.0)
        assert d1.global_id.startswith("G")

        # Second observation of same track with high similarity
        d2 = reid.observe("CAM-01", "T-1", vec, ts=101.0)
        assert d2.global_id == d1.global_id
        assert d2.matched is True

    def test_reid_topology_rejection_of_unlinked_hop(self):
        topo = CameraTopology()
        # CAM-01 and CAM-99 have no relationship
        reid = GlobalIdentityManager(
            similarity_threshold=0.60,
            topology=topo,
            use_topology=True,
        )
        vec = np.random.randn(512).astype(np.float32)
        vec = vec / np.linalg.norm(vec)

        d1 = reid.observe("CAM-01", "T-1", vec, ts=100.0)
        # Person suddenly observed on unlinked CAM-99 5 seconds later
        d2 = reid.observe("CAM-99", "T-2", vec, ts=105.0)

        # Because CAM-01 has configured edges but NO edge to CAM-99, it rejects merging!
        assert d2.global_id != d1.global_id

    def test_reid_topology_acceptance_of_plausible_hop(self):
        topo = CameraTopology()
        reid = GlobalIdentityManager(
            similarity_threshold=0.60,
            topology=topo,
            use_topology=True,
        )
        vec = np.random.randn(512).astype(np.float32)
        vec = vec / np.linalg.norm(vec)

        d1 = reid.observe("CAM-01", "T-1", vec, ts=100.0)
        # Plausible hop CAM-01 -> CAM-02 after 12 seconds (seeded avg is 10.0s)
        d2 = reid.observe("CAM-02", "T-5", vec, ts=112.0)

        assert d2.global_id == d1.global_id
        assert d2.matched is True
        assert "CAM-02" in reid.get_identity_summary(d1.global_id)["cameras"]

    @pytest.mark.anyio
    async def test_candidate_association_low_margin(self):
        mgr = get_entity_manager()
        cand = await mgr.record_candidate_association(
            source_entity_id="GLOBAL-PERSON-001",
            candidate_entity_id="GLOBAL-PERSON-002",
            confidence=0.68,
            signals={"appearance_sim": 0.68, "margin": 0.03},
            status="candidate",
        )
        assert cand.similarity_score == 0.68
        assert cand.candidate_entity_id == "GLOBAL-PERSON-002"
        assert cand.margin == 0.03

    @pytest.mark.anyio
    async def test_person_and_vehicle_profile(self):
        mgr = get_entity_manager()
        p_ent = await mgr.create_entity(entity_type="person", camera_id="CAM-01", local_track_id="P-1")
        v_ent = await mgr.create_entity(entity_type="vehicle", camera_id="CAM-01", local_track_id="V-1")

        p_prof = await mgr.get_person_profile(p_ent.display_id)
        assert p_prof is not None
        assert p_prof.display_id == p_ent.display_id
        assert p_prof.current_camera_id == "CAM-01"

        v_prof = await mgr.get_vehicle_profile(v_ent.display_id)
        assert v_prof is not None
        assert v_prof.display_id == v_ent.display_id
        assert v_prof.current_camera_id == "CAM-01"


class TestEntitiesAndTopologyAPI:
    """API endpoint verification for entities and topology."""

    def test_get_topology(self, client):
        resp = client.get("/api/topology")
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "edges" in data

    def test_evaluate_topology_api(self, client):
        resp = client.post(
            "/api/topology/evaluate",
            json={"from_camera": "CAM-01", "to_camera": "CAM-02", "elapsed_seconds": 10.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_plausible"] is True
        assert data["topology_score"] > 0.5

    def test_get_entities_list(self, client):
        resp = client.get("/api/entities")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
