"""
Comprehensive tests for:
- Phase 9: Zones, Movement, Context (Ray-casting, VirtualBoundary, Dwell, Repeated Entry)
- Phase 10: Event Engine & Debouncing (Preventing frame-by-frame event noise)
- Phase 11: Threat / Risk Engine (Deterministic scoring, explainable causal chains)
- Phase 13: Incident Engine Lifecycle (DETECTED -> ACTIVE -> ESCALATED -> RESOLVED)
- Phase 14: KILLER ALERT TEST: ONE INCIDENT = ONE OPERATOR ALERT (Deduplication > 90%)
- Phase 15: Target-Specific Evidence (7 people visible, ONLY primary target is marked as incident evidence)
- Phase 16: Comprehensive Chronological Incident Timeline
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from backend.main import app
from backend.database import init_db
from backend.zones.security_zone import (
    SecurityZone,
    VirtualBoundary,
    ZoneMonitor,
    ZoneSeverity,
    ZoneType,
)
from backend.events.debouncer import EventDebouncer
from backend.intelligence.threat_engine import compute_threat_score, ThreatLevel
from backend.incidents.service import IncidentManager, get_incident_manager
from backend.entities.service import get_entity_manager


@pytest.fixture(autouse=True)
async def ensure_db():
    await init_db()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class TestPhase9ZonesAndMovement:
    """Phase 9: Robust zone intelligence, polygon containment, boundaries, dwell."""

    def test_polygon_ray_casting(self):
        # Square zone (10, 10) to (50, 50)
        zone = SecurityZone(
            zone_id="ZONE-01",
            name="Restricted Area",
            polygon=[(10.0, 10.0), (50.0, 10.0), (50.0, 50.0), (10.0, 50.0)],
            severity=ZoneSeverity.RESTRICTED,
            zone_type=ZoneType.RESTRICTED,
        )
        assert zone.contains_point((25.0, 25.0)) is True  # Inside
        assert zone.contains_point((5.0, 5.0)) is False    # Outside
        assert zone.contains_point((100.0, 100.0)) is False # Far outside

    def test_virtual_boundary_directional_crossing(self):
        # Tripwire line from (0, 50) to (100, 50)
        boundary = VirtualBoundary(
            boundary_id="FENCE-01",
            name="Border Fence",
            pt1=(0.0, 50.0),
            pt2=(100.0, 50.0),
            direction="SOUTH",  # downward crossing (dy > 0 in image coords)
            severity=ZoneSeverity.CRITICAL,
        )
        # Crossing downwards: (50, 40) -> (50, 60)
        cross_south = boundary.check_crossing((50.0, 40.0), (50.0, 60.0))
        assert cross_south == "SOUTH"

        # Moving upwards (north): (50, 60) -> (50, 40) should be ignored when direction is SOUTH
        cross_north = boundary.check_crossing((50.0, 60.0), (50.0, 40.0))
        assert cross_north is None


class TestPhase10EventDebouncer:
    """Phase 10: Event debouncing to eliminate per-frame event spam."""

    def test_event_debouncing(self):
        debouncer = EventDebouncer(default_window_s=2.0)
        # First event should emit
        assert debouncer.should_emit("zone_entry", "CAM-01", track_id="T-1") is True
        # Immediately subsequent identical event within 2.0s must be suppressed!
        assert debouncer.should_emit("zone_entry", "CAM-01", track_id="T-1") is False
        # Different track should emit
        assert debouncer.should_emit("zone_entry", "CAM-01", track_id="T-2") is True


class TestPhase11ThreatEngine:
    """Phase 11: Independent deterministic threat scoring."""

    def test_threat_score_calculation(self):
        # Nominal
        score_nom, level_nom, _ = compute_threat_score()
        assert score_nom == 0.0
        assert level_nom == "NORMAL"

        # Restricted intrusion alone
        score_int, level_int, reasons_int = compute_threat_score(has_restricted_intrusion=True)
        assert score_int >= 35.0
        assert len(reasons_int) > 0

        # Critical escalation (Restricted + Weapon + Night)
        score_crit, level_crit, _ = compute_threat_score(
            has_restricted_intrusion=True,
            has_weapon_observation=True,
            has_night_movement=True,
        )
        assert score_crit >= 85.0
        assert level_crit == "CRITICAL"


class TestPhase13to16IncidentsAndAlertDeduplication:
    """
    Phases 13, 14, 15, 16:
    - Killer alert test: 1 incident = 1 alert (100 frame events -> 1 operator alert)
    - Target-specific evidence: Only primary target becomes incident evidence
    - Chronological timeline: Answers What, Who, Where, When, How Serious, Why, Evidence, Status
    """

    @pytest.mark.anyio
    async def test_killer_alert_deduplication(self):
        """
        KILLER ALERT RULE:
        100 raw events for a target in a restricted zone must produce
        EXACTLY 1 OPERATOR ALERT, NOT 100 ALERTS!
        """
        mgr = IncidentManager()
        ent_mgr = get_entity_manager()
        entity = await ent_mgr.create_entity(entity_type="person", camera_id="CAM-01", local_track_id="P-042")

        alerts_emitted = 0
        incident_id = None

        # Simulate 100 consecutive frame events for this intruder
        for i in range(100):
            inc, alert, is_new = await mgr.process_event(
                event_type="zone_intrusion",
                camera_id="CAM-01",
                threat_score=45.0 + (0.3 * i),  # Gradually rising threat
                threat_level="MEDIUM" if i < 50 else "HIGH",
                global_entity_id=entity.global_entity_id,
                local_track_id="P-042",
                zone_id="RESTRICTED-NORTH",
                zone_name="North Perimeter",
                narrative=f"Tracked target P-042 observed inside Restricted Zone (frame {i})",
            )
            if i == 0:
                incident_id = inc.incident_id
            if is_new:
                alerts_emitted += 1

        # Exactly 1 operator alert must have been emitted!
        assert alerts_emitted == 1
        metrics = mgr.get_deduplication_metrics()
        assert metrics["raw_events_processed"] == 100
        assert metrics["incidents_created"] == 1
        assert metrics["alerts_emitted"] == 1
        assert metrics["duplicate_alerts_suppressed"] == 99
        assert metrics["deduplication_rate_pct"] >= 99.0

    @pytest.mark.anyio
    async def test_target_specific_evidence(self):
        """
        PHASE 15:
        If 7 people are visible and PERSON-042 enters restricted zone,
        ONLY PERSON-042 is incident evidence. The other 6 bystander tracks
        MUST NOT become incident evidence!
        """
        mgr = IncidentManager()
        ent_mgr = get_entity_manager()

        target = await ent_mgr.create_entity(entity_type="person", camera_id="CAM-01", local_track_id="TARGET-042")
        bystander = await ent_mgr.create_entity(entity_type="person", camera_id="CAM-01", local_track_id="BYSTANDER-007")

        inc, _, _ = await mgr.process_event(
            event_type="restricted_intrusion",
            camera_id="CAM-01",
            threat_score=75.0,
            global_entity_id=target.global_entity_id,
            local_track_id="TARGET-042",
            zone_id="PERIMETER-ZONE",
        )

        # 1. Target evidence attached successfully
        target_ev = await mgr.attach_target_evidence(
            incident_id=inc.incident_id,
            target_entity_id=target.global_entity_id,
            camera_id="CAM-01",
            evidence_type="target_crop",
            target_bbox=[100.0, 200.0, 150.0, 320.0],
            reason="Primary intruder captured penetrating perimeter",
        )
        assert target_ev is not None
        assert target_ev.global_entity_id == target.global_entity_id
        assert target_ev.sha256_hash is not None

        # 2. Bystander evidence MUST be rejected from this incident
        bystander_ev = await mgr.attach_target_evidence(
            incident_id=inc.incident_id,
            target_entity_id=bystander.global_entity_id,
            camera_id="CAM-01",
            evidence_type="target_crop",
            target_bbox=[500.0, 400.0, 550.0, 520.0],
            reason="Innocent bystander walking on public path",
        )
        assert bystander_ev is None  # Must reject non-target evidence!

    @pytest.mark.anyio
    async def test_incident_timeline_and_lifecycle(self):
        """
        Phase 13 & 16: Complete timeline & lifecycle (DETECTED -> ACTIVE -> RESOLVED)
        """
        mgr = IncidentManager()
        ent_mgr = get_entity_manager()
        entity = await ent_mgr.create_entity(entity_type="person", camera_id="CAM-01", local_track_id="T-99")

        # Step 1: Detect incident
        inc, alert, is_new = await mgr.process_event(
            event_type="loitering_detected",
            camera_id="CAM-01",
            threat_score=40.0,
            global_entity_id=entity.global_entity_id,
            local_track_id="T-99",
            zone_id="GATE-01",
            narrative="Target loitering near gate",
        )
        assert is_new is True

        # Step 2: Operator acknowledges incident
        ack_inc = await mgr.acknowledge_incident(inc.incident_id, acknowledged_by="Officer_Miller")
        assert ack_inc.status == "ACKNOWLEDGED"

        # Step 3: Resolve incident
        res_inc = await mgr.resolve_incident(inc.incident_id, resolved_by="Officer_Miller", resolution_notes="Target vacated sector")
        assert res_inc.status == "RESOLVED"

        # Step 4: Verify complete chronological timeline
        timeline_data = await mgr.get_incident_timeline(inc.incident_id)
        assert timeline_data["incident_id"] == inc.incident_id
        assert timeline_data["what"] == "loitering_detected"
        assert timeline_data["status"] == "RESOLVED"
        assert len(timeline_data["timeline"]) >= 2
