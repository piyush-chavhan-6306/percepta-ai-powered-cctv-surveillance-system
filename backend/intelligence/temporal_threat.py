"""
Border Intelligence — Temporal Threat & Spatial Kinematics Engine.
Calculates deterministic temporal heuristics:
  1. Entity Influx Rate (linear polyfit rate-of-change of active targets over a sliding window)
  2. Coordinated Movement (vector cosine similarity of active Kalman velocities)
  3. Perimeter Closing Velocity (projection of velocity vector onto zone / boundary normal)
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
from typing import Dict, List, Optional, Tuple

import numpy as np

from backend.tracking.tracker import TrackedObject
from backend.zones.security_zone import SecurityZone, VirtualBoundary


@dataclass
class CoordinatedGroup:
    """Group of entities moving in tactical directional alignment."""
    track_ids: List[str]
    mean_cosine_similarity: float
    heading_deg: float
    member_count: int


@dataclass
class PerimeterClosingTarget:
    """Track actively closing towards a security zone or perimeter tripwire."""
    track_id: str
    boundary_or_zone_id: str
    boundary_name: str
    closing_speed_px_sec: float
    distance_to_boundary_px: float
    time_to_breach_sec: Optional[float] = None


@dataclass
class TemporalThreatSignal:
    """Consolidated temporal kinematics signal for threat engine integration."""
    camera_id: str
    timestamp: datetime
    # 1. Entity Influx
    entity_count: int = 0
    influx_slope_per_sec: float = 0.0
    has_rapid_influx: bool = False
    # 2. Coordinated Movement
    has_coordinated_movement: bool = False
    coordinated_groups: List[CoordinatedGroup] = field(default_factory=list)
    # 3. Perimeter Closing Velocity
    has_perimeter_closing: bool = False
    closing_targets: List[PerimeterClosingTarget] = field(default_factory=list)
    # Contextual Explanation
    contributing_factors: List[str] = field(default_factory=list)


def calculate_entity_influx_slope(
    history: List[Tuple[float, int]],
    min_points: int = 3,
    min_entities: int = 3,
    slope_threshold_per_sec: float = 0.40,
) -> Tuple[float, bool]:
    """
    Calculate the linear regression slope of entity counts over time (entities per second).

    Args:
        history: Chronological list of (timestamp_epoch_sec, entity_count).
        min_points: Minimum samples required to compute regression.
        min_entities: Minimum current entity count to qualify as potential crowd/group influx.
        slope_threshold_per_sec: Positive slope threshold (e.g. 0.40 entities/sec).

    Returns:
        (slope_per_sec, is_rapid_influx)
    """
    if not history or len(history) < min_points:
        return 0.0, False

    recent = history[-15:]  # Use last 15 samples
    ts = np.array([pt[0] for pt in recent], dtype=np.float64)
    counts = np.array([pt[1] for pt in recent], dtype=np.float64)

    dt = ts - ts[0]
    dt_var = np.var(dt)
    if dt_var < 1e-6:
        return 0.0, False

    # 1st-degree polynomial: count = slope * dt + intercept
    slope, _ = np.polyfit(dt, counts, 1)
    slope = float(slope)

    current_count = int(counts[-1])
    is_rapid = (slope >= slope_threshold_per_sec) and (current_count >= min_entities)

    return round(slope, 3), is_rapid


def compute_vector_cosine_similarity(
    v1: Tuple[float, float],
    v2: Tuple[float, float],
) -> float:
    """
    Compute cosine similarity between two 2D velocity vectors.
    Returns value in [-1.0, 1.0].
    """
    dx1, dy1 = float(v1[0]), float(v1[1])
    dx2, dy2 = float(v2[0]), float(v2[1])

    norm1 = math.hypot(dx1, dy1)
    norm2 = math.hypot(dx2, dy2)

    if norm1 < 1e-4 or norm2 < 1e-4:
        return 0.0

    dot = (dx1 * dx2) + (dy1 * dy2)
    cos_sim = dot / (norm1 * norm2)
    return max(-1.0, min(1.0, cos_sim))


def evaluate_coordinated_movement(
    tracks: List[TrackedObject],
    min_group_size: int = 2,
    min_speed_px_frame: float = 1.0,
    cosine_threshold: float = 0.70,  # ~45 deg alignment
    proximity_distance_px: float = 400.0,
) -> Tuple[bool, List[CoordinatedGroup]]:
    """
    Detect multiple moving tracks with directional velocity alignment (cosine similarity).

    Args:
        tracks: Active tracked objects in camera sector.
        min_group_size: Minimum number of aligned targets to constitute a group.
        min_speed_px_frame: Pixel displacement threshold to filter stationary noise.
        cosine_threshold: Cosine similarity cutoff (0.707 ≈ 45° alignment).
        proximity_distance_px: Maximum spatial separation between group members.

    Returns:
        (has_coordinated_movement, list_of_coordinated_groups)
    """
    moving_tracks = [
        t for t in tracks
        if (t.speed_px_per_frame >= min_speed_px_frame or math.hypot(t.velocity[0], t.velocity[1]) >= min_speed_px_frame)
    ]

    if len(moving_tracks) < min_group_size:
        return False, []

    # Find clusters of tracks moving in similar directions
    n = len(moving_tracks)
    visited = [False] * n
    groups: List[CoordinatedGroup] = []

    for i in range(n):
        if visited[i]:
            continue

        ti = moving_tracks[i]
        cluster = [ti]
        pair_cosines: List[float] = []

        for j in range(i + 1, n):
            if visited[j]:
                continue
            tj = moving_tracks[j]

            # Check spatial proximity
            dist = math.hypot(tj.center_x - ti.center_x, tj.center_y - ti.center_y)
            if dist > proximity_distance_px:
                continue

            cos_sim = compute_vector_cosine_similarity(ti.velocity, tj.velocity)
            if cos_sim >= cosine_threshold:
                cluster.append(tj)
                pair_cosines.append(cos_sim)
                visited[j] = True

        if len(cluster) >= min_group_size:
            visited[i] = True
            mean_cos = float(np.mean(pair_cosines)) if pair_cosines else 1.0
            mean_heading = float(np.mean([t.direction_deg for t in cluster]))
            groups.append(
                CoordinatedGroup(
                    track_ids=[str(t.track_id) for t in cluster],
                    mean_cosine_similarity=round(mean_cos, 3),
                    heading_deg=round(mean_heading, 1),
                    member_count=len(cluster),
                )
            )

    return (len(groups) > 0), groups


def project_velocity_to_boundary_normal(
    track_center: Tuple[float, float],
    velocity: Tuple[float, float],
    pt1: Tuple[float, float],
    pt2: Tuple[float, float],
    fps: float = 30.0,
) -> Tuple[float, float]:
    """
    Calculate Euclidean distance to a line segment and closing speed towards it.

    Returns:
        (distance_px, closing_speed_px_sec)
        Positive closing_speed indicates target is moving towards the segment.
    """
    x0, y0 = float(track_center[0]), float(track_center[1])
    vx, vy = float(velocity[0]), float(velocity[1])
    x1, y1 = float(pt1[0]), float(pt1[1])
    x2, y2 = float(pt2[0]), float(pt2[1])

    # Segment vector S
    dx = x2 - x1
    dy = y2 - y1
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq < 1e-6:
        dist = math.hypot(x0 - x1, y0 - y1)
        return dist, 0.0

    # Projection parameter t of point onto line
    t = max(0.0, min(1.0, ((x0 - x1) * dx + (y0 - y1) * dy) / seg_len_sq))
    nearest_x = x1 + t * dx
    nearest_y = y1 + t * dy

    # Vector from target to nearest point on boundary: D = P_nearest - P_track
    to_bound_x = nearest_x - x0
    to_bound_y = nearest_y - y0
    dist = math.hypot(to_bound_x, to_bound_y)

    if dist < 1e-4:
        return 0.0, 0.0

    # Unit direction from target toward boundary: d_hat
    d_hat_x = to_bound_x / dist
    d_hat_y = to_bound_y / dist

    # Closing velocity is projection of track velocity onto d_hat
    # Positive means closing the gap, negative means moving away
    closing_px_frame = (vx * d_hat_x) + (vy * d_hat_y)
    closing_px_sec = closing_px_frame * fps

    return round(dist, 1), round(closing_px_sec, 1)


def evaluate_perimeter_closing_velocity(
    tracks: List[TrackedObject],
    boundaries: List[VirtualBoundary],
    zones: List[SecurityZone],
    max_proximity_px: float = 350.0,
    min_closing_speed_px_sec: float = 25.0,
    fps: float = 30.0,
) -> Tuple[bool, List[PerimeterClosingTarget]]:
    """
    Detect targets actively closing towards any configured virtual boundary or zone perimeter.
    """
    closing_targets: List[PerimeterClosingTarget] = []

    for t in tracks:
        if t.speed_px_per_frame < 0.5:
            continue

        center = (t.center_x, t.center_y)
        vel = (t.velocity[0], t.velocity[1])

        # Check virtual boundaries (tripwires)
        for b in boundaries:
            if not b.is_active:
                continue
            dist, closing_speed = project_velocity_to_boundary_normal(
                center, vel, b.pt1, b.pt2, fps=fps
            )
            if dist <= max_proximity_px and closing_speed >= min_closing_speed_px_sec:
                ttb = round(dist / closing_speed, 1) if closing_speed > 0.0 else None
                closing_targets.append(
                    PerimeterClosingTarget(
                        track_id=str(t.track_id),
                        boundary_or_zone_id=b.boundary_id,
                        boundary_name=b.name,
                        closing_speed_px_sec=closing_speed,
                        distance_to_boundary_px=dist,
                        time_to_breach_sec=ttb,
                    )
                )

        # Check security zone perimeter segments
        for z in zones:
            if not z.is_active or len(z.polygon) < 3:
                continue
            poly = z.polygon
            for idx in range(len(poly)):
                p1 = poly[idx]
                p2 = poly[(idx + 1) % len(poly)]
                dist, closing_speed = project_velocity_to_boundary_normal(
                    center, vel, p1, p2, fps=fps
                )
                if dist <= max_proximity_px and closing_speed >= min_closing_speed_px_sec:
                    ttb = round(dist / closing_speed, 1) if closing_speed > 0.0 else None
                    closing_targets.append(
                        PerimeterClosingTarget(
                            track_id=str(t.track_id),
                            boundary_or_zone_id=z.zone_id,
                            boundary_name=z.name,
                            closing_speed_px_sec=closing_speed,
                            distance_to_boundary_px=dist,
                            time_to_breach_sec=ttb,
                        )
                    )
                    break  # Tag once per zone

    return (len(closing_targets) > 0), closing_targets


class TemporalThreatAnalyzer:
    """
    Maintains rolling count history and computes real-time kinematic & temporal signals.
    """

    def __init__(self, history_window_sec: float = 10.0) -> None:
        self.history_window_sec = history_window_sec
        # camera_id -> list of (timestamp_epoch, count)
        self._count_history: Dict[str, List[Tuple[float, int]]] = {}

    def record_frame_counts(self, camera_id: str, count: int, timestamp: Optional[float] = None) -> None:
        """Record the active target count for a camera at this moment."""
        t = timestamp or datetime.now(timezone.utc).timestamp()
        if camera_id not in self._count_history:
            self._count_history[camera_id] = []

        hist = self._count_history[camera_id]
        hist.append((t, count))

        # Prune older than history_window_sec
        cutoff = t - self.history_window_sec
        self._count_history[camera_id] = [pt for pt in hist if pt[0] >= cutoff]

    def analyze_camera(
        self,
        camera_id: str,
        tracks: List[TrackedObject],
        boundaries: Optional[List[VirtualBoundary]] = None,
        zones: Optional[List[SecurityZone]] = None,
        fps: float = 30.0,
    ) -> TemporalThreatSignal:
        """Analyze temporal and kinematic factors for a camera stream."""
        now = datetime.now(timezone.utc)
        now_ts = now.timestamp()
        self.record_frame_counts(camera_id, len(tracks), timestamp=now_ts)

        factors: List[str] = []

        # 1. Entity Influx Slope
        hist = self._count_history.get(camera_id, [])
        slope, has_influx = calculate_entity_influx_slope(hist)
        if has_influx:
            factors.append(f"Rapid Entity Influx: +{slope:.2f} entities/sec (Sector Density Rising)")

        # 2. Coordinated Movement
        has_coord, coord_groups = evaluate_coordinated_movement(tracks)
        if has_coord:
            for g in coord_groups:
                factors.append(
                    f"Coordinated Movement: {g.member_count} targets aligned (Heading {g.heading_deg}°, cos={g.mean_cosine_similarity})"
                )

        # 3. Perimeter Closing Velocity
        has_closing, closing_targets = evaluate_perimeter_closing_velocity(
            tracks, boundaries or [], zones or [], fps=fps
        )
        if has_closing:
            for ct in closing_targets:
                eta_str = f"ETA ~{ct.time_to_breach_sec}s" if ct.time_to_breach_sec else "Approaching"
                factors.append(
                    f"Perimeter Closing Vector: Target {ct.track_id} closing on '{ct.boundary_name}' at {ct.closing_speed_px_sec} px/s ({eta_str})"
                )

        return TemporalThreatSignal(
            camera_id=camera_id,
            timestamp=now,
            entity_count=len(tracks),
            influx_slope_per_sec=slope,
            has_rapid_influx=has_influx,
            has_coordinated_movement=has_coord,
            coordinated_groups=coord_groups,
            has_perimeter_closing=has_closing,
            closing_targets=closing_targets,
            contributing_factors=factors,
        )


_global_temporal_analyzer = TemporalThreatAnalyzer()


def get_temporal_threat_analyzer() -> TemporalThreatAnalyzer:
    return _global_temporal_analyzer
