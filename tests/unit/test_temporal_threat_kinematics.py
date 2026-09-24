"""
Unit Tests for PERCEPTA Temporal Threat & Kinematics Engine.
Verifies entity influx slopes, vector cosine coordination, and perimeter closing velocity.
"""
from datetime import datetime, timezone
import pytest

from backend.intelligence.temporal_threat import (
    calculate_entity_influx_slope,
    compute_vector_cosine_similarity,
    evaluate_coordinated_movement,
    project_velocity_to_boundary_normal,
    evaluate_perimeter_closing_velocity,
    get_temporal_threat_analyzer,
)
from backend.intelligence.threat_engine import compute_threat_score
from backend.tracking.tracker import TrackedObject
from backend.zones.security_zone import SecurityZone, VirtualBoundary, ZoneSeverity


def test_entity_influx_slope_detection():
    # 1. Flat count: no influx
    flat_history = [(float(i), 2) for i in range(10)]
    slope, is_rapid = calculate_entity_influx_slope(flat_history)
    assert slope == 0.0
    assert not is_rapid

    # 2. Rapid climb: 2 -> 3 -> 5 -> 7 -> 9 over 5 seconds (slope ≈ 1.7 entities/sec)
    climb_history = [
        (0.0, 2),
        (1.0, 3),
        (2.0, 5),
        (3.0, 7),
        (4.0, 9),
    ]
    slope, is_rapid = calculate_entity_influx_slope(climb_history)
    assert slope > 0.5
    assert is_rapid is True


def test_vector_cosine_similarity_and_coordination():
    # Identical direction: cosine = 1.0
    cos_same = compute_vector_cosine_similarity((10.0, 0.0), (15.0, 0.0))
    assert pytest.approx(cos_same, 0.01) == 1.0

    # Opposite direction: cosine = -1.0
    cos_opp = compute_vector_cosine_similarity((10.0, 0.0), (-10.0, 0.0))
    assert pytest.approx(cos_opp, 0.01) == -1.0

    # Perpendicular: cosine = 0.0
    cos_perp = compute_vector_cosine_similarity((10.0, 0.0), (0.0, 10.0))
    assert pytest.approx(cos_perp, 0.01) == 0.0

    # Test group evaluation with TrackedObjects
    now = datetime.now(timezone.utc)
    t1 = TrackedObject(
        track_id="T1",
        object_class="person",
        confidence=0.9,
        bounding_box=[100, 100, 150, 200],
        normalized_box=[0.1, 0.1, 0.15, 0.2],
        frame_number=1,
        timestamp=now,
        center_x=120.0,
        center_y=150.0,
        velocity=(8.0, 2.0),
        speed_px_per_frame=8.2,
        direction_deg=14.0,
    )
    t2 = TrackedObject(
        track_id="T2",
        object_class="person",
        confidence=0.88,
        bounding_box=[130, 110, 180, 210],
        normalized_box=[0.13, 0.11, 0.18, 0.21],
        frame_number=1,
        timestamp=now,
        center_x=150.0,
        center_y=160.0,
        velocity=(8.5, 2.2),
        speed_px_per_frame=8.7,
        direction_deg=14.5,
    )
    t3_unrelated = TrackedObject(
        track_id="T3",
        object_class="person",
        confidence=0.85,
        bounding_box=[400, 400, 450, 500],
        normalized_box=[0.4, 0.4, 0.45, 0.5],
        frame_number=1,
        timestamp=now,
        center_x=420.0,
        center_y=450.0,
        velocity=(-5.0, 8.0),
        speed_px_per_frame=9.4,
        direction_deg=122.0,
    )

    has_coord, groups = evaluate_coordinated_movement([t1, t2, t3_unrelated])
    assert has_coord is True
    assert len(groups) == 1
    assert "T1" in groups[0].track_ids and "T2" in groups[0].track_ids
    assert "T3" not in groups[0].track_ids
    assert groups[0].mean_cosine_similarity >= 0.95


def test_perimeter_closing_velocity():
    # Tripwire across y = 400 from x=100 to x=900
    boundary = VirtualBoundary(
        boundary_id="TEST_FENCE_01",
        name="Sector North Tripwire",
        pt1=(100.0, 400.0),
        pt2=(900.0, 400.0),
        severity=ZoneSeverity.CRITICAL,
    )

    # 1. Target at (500, 300) moving downwards at vy = 10 px/frame (towards fence)
    dist, closing_speed = project_velocity_to_boundary_normal(
        track_center=(500.0, 300.0),
        velocity=(0.0, 10.0),
        pt1=boundary.pt1,
        pt2=boundary.pt2,
        fps=30.0,
    )
    assert dist == 100.0
    assert closing_speed == 300.0  # 10 px/frame * 30 fps

    # 2. Target at (500, 300) moving upwards away from fence (vy = -10)
    dist_away, closing_speed_away = project_velocity_to_boundary_normal(
        track_center=(500.0, 300.0),
        velocity=(0.0, -10.0),
        pt1=boundary.pt1,
        pt2=boundary.pt2,
        fps=30.0,
    )
    assert dist_away == 100.0
    assert closing_speed_away == -300.0  # moving away

    # Test evaluate_perimeter_closing_velocity
    now = datetime.now(timezone.utc)
    target = TrackedObject(
        track_id="INTRUDER_01",
        object_class="person",
        confidence=0.92,
        bounding_box=[480, 260, 520, 340],
        normalized_box=[0.48, 0.26, 0.52, 0.34],
        frame_number=10,
        timestamp=now,
        center_x=500.0,
        center_y=300.0,
        velocity=(0.0, 8.0),
        speed_px_per_frame=8.0,
    )

    has_closing, closing_list = evaluate_perimeter_closing_velocity(
        tracks=[target],
        boundaries=[boundary],
        zones=[],
        fps=30.0,
    )
    assert has_closing is True
    assert len(closing_list) == 1
    assert closing_list[0].track_id == "INTRUDER_01"
    assert closing_list[0].boundary_or_zone_id == "TEST_FENCE_01"
    assert closing_list[0].closing_speed_px_sec == 240.0
    assert closing_list[0].time_to_breach_sec == pytest.approx(0.4, 0.1)


def test_threat_score_with_temporal_factors():
    # Test baseline vs temporal boost
    base_score, base_level, _ = compute_threat_score()
    assert base_score == 0.0
    assert base_level == "NORMAL"

    score_influx, level_influx, reasons_influx = compute_threat_score(has_rapid_influx=True)
    assert score_influx == 10.0
    assert any("Rapid Target Influx" in r for r in reasons_influx)

    score_coord, level_coord, reasons_coord = compute_threat_score(has_coordinated_movement=True)
    assert score_coord == 15.0
    assert any("Coordinated Target Movement" in r for r in reasons_coord)

    score_combo, level_combo, reasons_combo = compute_threat_score(
        has_rapid_influx=True,
        has_coordinated_movement=True,
        has_perimeter_closing=True,
        has_night_movement=True,
    )
    assert score_combo >= 55.0
    assert level_combo in ("HIGH", "CRITICAL")
