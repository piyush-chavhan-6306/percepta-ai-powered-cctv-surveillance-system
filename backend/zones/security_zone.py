from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

from backend.events.schema import AlertEvent, EventType, SourceType, ZoneEvent
from backend.events.store import EventStore, get_event_store

if TYPE_CHECKING:
    from backend.tracking.tracker import TrackedObject

logger = logging.getLogger(__name__)

# These were shipped as demonstration rules, not operator-created rules. Keep
# their saved definitions for recovery, but never activate them automatically.
BUILT_IN_DEMO_RULE_IDS = {"BORDER_RESTRICTED_STRIP_01", "VIRTUAL_PERIMETER_FENCE_01"}


class ZoneSeverity(str, Enum):
    NORMAL = "normal"
    RESTRICTED = "restricted"
    CRITICAL = "critical"

    # Backward compatibility aliases
    INFO = "normal"
    WARNING = "restricted"

    @classmethod
    def from_str(cls, val: Any) -> "ZoneSeverity":
        if isinstance(val, cls):
            return val
        s = str(val or "").strip().lower()
        if s in ("critical", "high"):
            return cls.CRITICAL
        elif s in ("restricted", "warning", "medium"):
            return cls.RESTRICTED
        else:
            return cls.NORMAL


class ZoneType(str, Enum):
    """Zone functional types per Phase 9 spec."""
    NORMAL = "normal"
    RESTRICTED = "restricted"
    SENSITIVE = "sensitive"
    CRITICAL = "critical"
    ENTRY = "entry"
    EXIT = "exit"

    @classmethod
    def from_str(cls, val: Any) -> "ZoneType":
        if isinstance(val, cls):
            return val
        s = str(val or "").strip().lower()
        for member in cls:
            if member.value == s:
                return member
        return cls.NORMAL


@dataclass
class SecurityZone:
    """
    Polygon or rectangular restricted zone.
    Coordinates are defined as a list of (x, y) vertices forming a closed polygon.
    """
    zone_id: str
    name: str
    polygon: List[Tuple[float, float]]  # [(x0, y0), (x1, y1), ...]
    severity: ZoneSeverity = ZoneSeverity.RESTRICTED
    zone_type: ZoneType = ZoneType.NORMAL
    is_active: bool = True
    target_classes: Optional[Set[str]] = None  # None means all classes
    loitering_threshold_seconds: Optional[float] = None  # None = no loitering check
    loitering_debounce_seconds: float = 30.0  # Cooldown between repeat loitering alerts
    persistence_threshold_seconds: Optional[float] = None  # Escalation for long dwell
    entry_count_threshold: int = 2  # Repeated entry alert after N entries

    def contains_point(self, point: Tuple[float, float]) -> bool:
        """
        Ray-casting algorithm to test if a 2D point (x, y) is inside the polygon.
        Supports both normalized [0.0, 1.0] and pixel coordinate domains.
        """
        if not self.polygon or len(self.polygon) < 3 or point is None:
            return False

        x, y = float(point[0]), float(point[1])
        poly = self.polygon
        n = len(poly)

        # Check if polygon is normalized [0.0, 1.0] while point is in pixel coordinates
        is_poly_norm = all(0.0 <= float(p[0]) <= 1.0 and 0.0 <= float(p[1]) <= 1.0 for p in poly)
        if is_poly_norm and (x > 1.0 or y > 1.0):
            # Point is in pixels, scale down (assume 1280x720 or 1920x1080)
            base_w = 1920.0 if x > 1280 else 1280.0
            base_h = 1080.0 if y > 720 else 720.0
            x = x / base_w
            y = y / base_h
        elif not is_poly_norm and (x <= 1.0 and y <= 1.0):
            # Polygon is in pixels, point is normalized
            poly_max_x = max(float(p[0]) for p in poly)
            poly_max_y = max(float(p[1]) for p in poly)
            base_w = 1920.0 if poly_max_x > 1280 else 1280.0
            base_h = 1080.0 if poly_max_y > 720 else 720.0
            x = x * base_w
            y = y * base_h

        inside = False
        p1x, p1y = float(poly[0][0]), float(poly[0][1])
        for i in range(1, n + 1):
            p2x, p2y = float(poly[i % n][0]), float(poly[i % n][1])
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        else:
                            xinters = p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y

        return inside


@dataclass
class VirtualBoundary:
    """
    Virtual fence or border tripwire defined by a directed 2D line segment (pt1 -> pt2).
    Tracks traversing from one side of the line to another generate crossing events.
    """
    boundary_id: str
    name: str
    pt1: Tuple[float, float]  # (x1, y1)
    pt2: Tuple[float, float]  # (x2, y2)
    severity: ZoneSeverity = ZoneSeverity.CRITICAL
    direction: str = "BIDIRECTIONAL"  # "NORTH", "SOUTH", "EAST", "WEST", "BIDIRECTIONAL"
    debounce_seconds: float = 3.0
    is_active: bool = True
    target_classes: Optional[Set[str]] = None

    def check_crossing(
        self,
        prev_point: Tuple[float, float],
        curr_point: Tuple[float, float],
    ) -> Optional[str]:
        """
        Check if the movement segment (prev_point -> curr_point) crosses this boundary.
        Supports both normalized [0.0, 1.0] and pixel coordinate domains.
        Returns crossing direction or None.
        """
        if prev_point is None or curr_point is None:
            return None

        p0_x, p0_y = float(prev_point[0]), float(prev_point[1])
        p1_x, p1_y = float(curr_point[0]), float(curr_point[1])
        q0_x, q0_y = float(self.pt1[0]), float(self.pt1[1])
        q1_x, q1_y = float(self.pt2[0]), float(self.pt2[1])

        # Normalize or match coordinate spaces
        is_bound_norm = (0.0 <= q0_x <= 1.0 and 0.0 <= q0_y <= 1.0 and
                         0.0 <= q1_x <= 1.0 and 0.0 <= q1_y <= 1.0)
        is_pt_norm = (max(abs(p0_x), abs(p1_x)) <= 1.0 and max(abs(p0_y), abs(p1_y)) <= 1.0)

        if is_bound_norm and not is_pt_norm:
            # Scale point down to [0.0, 1.0]
            base_w = 1920.0 if max(p0_x, p1_x) > 1280 else 1280.0
            base_h = 1080.0 if max(p0_y, p1_y) > 720 else 720.0
            p0_x, p1_x = p0_x / base_w, p1_x / base_w
            p0_y, p1_y = p0_y / base_h, p1_y / base_h
        elif not is_bound_norm and is_pt_norm:
            # Scale boundary down or point up
            base_w = 1920.0 if max(q0_x, q1_x) > 1280 else 1280.0
            base_h = 1080.0 if max(q0_y, q1_y) > 720 else 720.0
            p0_x, p1_x = p0_x * base_w, p1_x * base_w
            p0_y, p1_y = p0_y * base_h, p1_y * base_h

        # Check line segment intersection between (P0 -> P1) and (Q0 -> Q1)
        def _ccw(a: Tuple[float, float], b: Tuple[float, float], c: Tuple[float, float]) -> float:
            return (c[1] - a[1]) * (b[0] - a[0]) - (b[1] - a[1]) * (c[0] - a[0])

        p0, p1 = (p0_x, p0_y), (p1_x, p1_y)
        q0, q1 = (q0_x, q0_y), (q1_x, q1_y)

        # Check orientations
        d1 = _ccw(q0, q1, p0)
        d2 = _ccw(q0, q1, p1)
        d3 = _ccw(p0, p1, q0)
        d4 = _ccw(p0, p1, q1)

        # Proper intersection
        if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and \
           ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
            displacement = ((p1_x - p0_x) ** 2 + (p1_y - p0_y) ** 2) ** 0.5
            min_disp = 0.0015 if is_bound_norm else 2.5
            if displacement < min_disp:
                return None

            req_dir = (self.direction or "BIDIRECTIONAL").upper().strip()
            dx = p1_x - p0_x
            dy = p1_y - p0_y

            # Direction filtering with operator aliases
            if req_dir in ("NORTH", "UP", "INWARD") and dy >= 0:
                return None
            elif req_dir in ("SOUTH", "DOWN", "OUTWARD") and dy <= 0:
                return None
            elif req_dir in ("EAST", "RIGHT", "LEFT_TO_RIGHT") and dx <= 0:
                return None
            elif req_dir in ("WEST", "LEFT", "RIGHT_TO_LEFT") and dx >= 0:
                return None
            elif req_dir in ("INBOUND", "A_TO_B") and not (d1 > 0 and d2 < 0):
                return None
            elif req_dir in ("OUTBOUND", "B_TO_A") and not (d1 < 0 and d2 > 0):
                return None

            if req_dir in ("NORTH", "SOUTH", "EAST", "WEST", "LEFT_TO_RIGHT", "RIGHT_TO_LEFT", "INWARD", "OUTWARD"):
                return req_dir

            # Default / BIDIRECTIONAL: determine direction relative to line segment orientation
            if d1 > 0 and d2 < 0:
                return "inbound"
            else:
                return "outbound"

        return None


@dataclass
class ZoneTransition:
    """Represents a state change for a tracked object in relation to a zone/boundary."""
    track_id: str
    zone_id: str
    zone_name: str
    severity: str
    transition_type: str  # "entered", "exited", "crossed", "dwelling", "loitering"
    frame_number: int
    timestamp: datetime
    camera_id: str
    position: Tuple[float, float]
    object_class: str
    dwell_duration_seconds: Optional[float] = None


class ZoneMonitor:
    """
    Monitors tracked objects across configured security zones and virtual boundaries.
    Maintains track-zone occupancy states, dwell durations, and enforces the rules:
    - Normal presence alone is NOT an intrusion alert spam.
    - Security alerts fire on state transitions (entry, boundary crossing).
    - Loitering alerts fire ONLY when dwell duration exceeds configured threshold (debounced).
    """

    def __init__(
        self,
        zones: Optional[List[SecurityZone]] = None,
        boundaries: Optional[List[VirtualBoundary]] = None,
        event_store: Optional[EventStore] = None,
        load_persistence: bool = True,
        suppress_initial_entry: bool = False,
    ) -> None:
        self.zones: Dict[str, SecurityZone] = {z.zone_id: z for z in (zones or [])}
        self.boundaries: Dict[str, VirtualBoundary] = {b.boundary_id: b for b in (boundaries or [])}
        self.event_store = event_store or get_event_store()
        self.suppress_initial_entry = suppress_initial_entry

        # Track state tracking: {track_id: {zone_id: is_inside}}
        self._track_zone_state: Dict[str, Dict[str, bool]] = {}
        # Track entry timestamps: {track_id: {zone_id: entry_datetime}}
        self._track_zone_entry_time: Dict[str, Dict[str, datetime]] = {}
        # Track last loitering alert timestamps: {track_id: {zone_id: last_alert_datetime}}
        self._track_zone_loiter_alert_time: Dict[str, Dict[str, datetime]] = {}
        # Track previous positions for boundary crossings: {track_id: (x, y)}
        self._track_prev_positions: Dict[str, Tuple[float, float]] = {}
        # Track last boundary crossing alert timestamps: {track_id: {boundary_id: last_alert_datetime}}
        self._track_boundary_alert_time: Dict[str, Dict[str, datetime]] = {}
        # One operator notification per target across all zone/tripwire rules.
        self._track_operator_alert_time: Dict[str, datetime] = {}
        self._track_operator_last_severity: Dict[str, int] = {}
        self.operator_alert_cooldown_seconds = 8.0
        # Repeated entry tracking: {track_id: {zone_id: entry_count}}
        self._track_zone_entry_count: Dict[str, Dict[str, int]] = {}
        # Persistence escalation: {track_id: {zone_id: first_entry_datetime}}
        self._track_zone_first_entry: Dict[str, Dict[str, datetime]] = {}
        # Persistence alert debounce: {track_id: {zone_id: last_persistence_alert_datetime}}
        self._track_zone_persistence_alert_time: Dict[str, Dict[str, datetime]] = {}

        if load_persistence and not zones and not boundaries:
            self.load_persistent_definitions()

    @classmethod
    def with_shared_definitions(cls, source: "ZoneMonitor") -> "ZoneMonitor":
        """
        Build a monitor that shares `source`'s zone/boundary definitions by
        reference but keeps its own per-track state.
        """
        monitor = cls(event_store=source.event_store, load_persistence=False, suppress_initial_entry=False)
        monitor.zones = source.zones
        monitor.boundaries = source.boundaries
        return monitor

    def load_persistent_definitions(self, filepath: Optional[str] = None) -> None:
        """Load persistent zones and boundaries from JSON storage."""
        import json
        from pathlib import Path
        fp = filepath or getattr(self, "persistence_filepath", "storage/zones_config.json")
        self.persistence_filepath = fp
        p = Path(fp)
        if not p.exists():
            return
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            for zd in data.get("zones", []):
                z = SecurityZone(
                    zone_id=zd["zone_id"],
                    name=zd["name"],
                    polygon=[tuple(pt) for pt in zd["polygon"]],
                    severity=ZoneSeverity.from_str(zd.get("severity", "restricted")),
                    is_active=zd.get("is_active", True) and zd["zone_id"] not in BUILT_IN_DEMO_RULE_IDS,
                    loitering_threshold_seconds=zd.get("loitering_threshold_seconds"),
                    loitering_debounce_seconds=zd.get("loitering_debounce_seconds", 30.0),
                )
                self.zones[z.zone_id] = z
            for bd in data.get("boundaries", []):
                b = VirtualBoundary(
                    boundary_id=bd["boundary_id"],
                    name=bd["name"],
                    pt1=tuple(bd["pt1"]),
                    pt2=tuple(bd["pt2"]),
                    severity=ZoneSeverity.from_str(bd.get("severity", "critical")),
                    direction=bd.get("direction", "BIDIRECTIONAL"),
                    debounce_seconds=bd.get("debounce_seconds", 3.0),
                    is_active=bd.get("is_active", True) and bd["boundary_id"] not in BUILT_IN_DEMO_RULE_IDS,
                )
                self.boundaries[b.boundary_id] = b
            logger.info(f"Loaded {len(self.zones)} zones and {len(self.boundaries)} boundaries from {fp}")
        except Exception as err:
            logger.warning(f"Failed to load zones from {fp}: {err}")

    def save_persistent_definitions(self, filepath: Optional[str] = None) -> None:
        """Save active zones and boundaries to JSON storage."""
        import json
        from pathlib import Path
        fp = filepath or getattr(self, "persistence_filepath", "storage/zones_config.json")
        self.persistence_filepath = fp
        p = Path(fp)
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = {
                "zones": [
                    {
                        "zone_id": z.zone_id,
                        "name": z.name,
                        "polygon": [list(pt) for pt in z.polygon],
                        "severity": z.severity.value,
                        "is_active": z.is_active,
                        "loitering_threshold_seconds": z.loitering_threshold_seconds,
                        "loitering_debounce_seconds": z.loitering_debounce_seconds,
                    }
                    for z in self.zones.values()
                ],
                "boundaries": [
                    {
                        "boundary_id": b.boundary_id,
                        "name": b.name,
                        "pt1": list(b.pt1),
                        "pt2": list(b.pt2),
                        "severity": b.severity.value,
                        "direction": getattr(b, "direction", "BIDIRECTIONAL"),
                        "debounce_seconds": b.debounce_seconds,
                        "is_active": b.is_active,
                    }
                    for b in self.boundaries.values()
                ],
            }
            with open(p, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved {len(self.zones)} zones and {len(self.boundaries)} boundaries to {filepath}")
        except Exception as err:
            logger.warning(f"Failed to save zones to {filepath}: {err}")

    def add_zone(self, zone: SecurityZone) -> None:
        self.zones[zone.zone_id] = zone
        self.save_persistent_definitions()

    def remove_zone(self, zone_id: str) -> bool:
        if zone_id in self.zones:
            del self.zones[zone_id]
            for t_id in list(self._track_zone_state.keys()):
                self._track_zone_state[t_id].pop(zone_id, None)
                self._track_zone_entry_time[t_id].pop(zone_id, None)
                self._track_zone_loiter_alert_time[t_id].pop(zone_id, None)
            self.save_persistent_definitions()
            return True
        return False

    def add_boundary(self, boundary: VirtualBoundary) -> None:
        self.boundaries[boundary.boundary_id] = boundary
        self.save_persistent_definitions()

    def remove_boundary(self, boundary_id: str) -> bool:
        if boundary_id in self.boundaries:
            del self.boundaries[boundary_id]
            for t_id in list(self._track_boundary_alert_time.keys()):
                self._track_boundary_alert_time[t_id].pop(boundary_id, None)
            self.save_persistent_definitions()
            return True
        return False

    def reset(self) -> None:
        """Reset internal occupancy states, boundary debounces, and dwell clocks."""
        self._track_zone_state.clear()
        self._track_zone_entry_time.clear()
        self._track_zone_loiter_alert_time.clear()
        self._track_prev_positions.clear()
        self._track_boundary_alert_time.clear()
        self._track_operator_alert_time.clear()
        self._track_operator_last_severity.clear()
        self._track_zone_entry_count.clear()
        self._track_zone_first_entry.clear()
        self._track_zone_persistence_alert_time.clear()

    def evaluate_tracks(
        self,
        tracks: List[TrackedObject],
        camera_id: str,
        source: SourceType = SourceType.VIDEO_FILE,
    ) -> Tuple[List[ZoneEvent], List[AlertEvent]]:
        """
        Evaluate current frame tracks against all zones and boundaries.
        Generates structured narrative events, causal chains, and deterministic threat scores.
        """
        from backend.intelligence.threat_engine import compute_threat_score
        from backend.tracking.movement import is_moving_towards

        zone_events: List[ZoneEvent] = []
        alert_events: List[AlertEvent] = []

        active_track_ids = {t.track_id for t in tracks}
        now_dt = datetime.now(timezone.utc)
        is_night = (now_dt.hour >= 22 or now_dt.hour < 5)

        # Precompute centroids of critical/restricted zones for approach detection
        protected_centroids: List[Tuple[float, float]] = []
        for zone in self.zones.values():
            if zone.is_active and zone.severity in (ZoneSeverity.RESTRICTED, ZoneSeverity.CRITICAL):
                if zone.polygon and len(zone.polygon) >= 3:
                    cx = sum(p[0] for p in zone.polygon) / len(zone.polygon)
                    cy = sum(p[1] for p in zone.polygon) / len(zone.polygon)
                    protected_centroids.append((cx, cy))

        for track in tracks:
            t_id = track.track_id
            curr_pos = (track.center_x, track.center_y)
            prev_pos = self._track_prev_positions.get(t_id)

            if t_id not in self._track_zone_state:
                self._track_zone_state[t_id] = {}
            if t_id not in self._track_zone_entry_time:
                self._track_zone_entry_time[t_id] = {}
            if t_id not in self._track_zone_loiter_alert_time:
                self._track_zone_loiter_alert_time[t_id] = {}

            heading = getattr(track, "cardinal_heading", "STATIONARY")
            dir_deg = getattr(track, "direction_deg", 0.0)
            heading_protected = False

            if heading != "STATIONARY" and protected_centroids:
                for pc in protected_centroids:
                    if is_moving_towards(curr_pos, dir_deg, pc, tolerance_deg=50.0):
                        heading_protected = True
                        break

            track.heading_towards_protected = heading_protected
            track.is_night_movement = is_night

            # 1. Evaluate Polygon Zones & Loitering
            for z_id, zone in self.zones.items():
                if not zone.is_active:
                    continue
                if zone.target_classes and track.object_class not in zone.target_classes:
                    continue

                is_inside = zone.contains_point(curr_pos) or (
                    hasattr(track, "bbox") and track.bbox and len(track.bbox) >= 4 and zone.contains_point((track.center_x, float(track.bbox[3])))
                )
                zone_state = self._track_zone_state[t_id]
                has_prior_zone_state = z_id in zone_state
                was_inside = zone_state.get(z_id, False)

                # A video often starts with many targets already visible inside
                # a drawn zone. That first observation is baseline occupancy,
                # not a verified crossing, otherwise startup produces a burst
                # of false intrusion alerts. A later outside-to-inside change
                # remains a normal, alerting entry transition.
                if not has_prior_zone_state:
                    if self.suppress_initial_entry:
                        zone_state[z_id] = is_inside
                        if is_inside:
                            self._track_zone_entry_time[t_id][z_id] = track.timestamp
                        continue
                    else:
                        zone_state[z_id] = False

                if is_inside and not was_inside:
                    # STATE TRANSITION: ENTERED
                    self._track_zone_state[t_id][z_id] = True
                    self._track_zone_entry_time[t_id][z_id] = track.timestamp
                    track.previous_zone = track.current_zone
                    track.current_zone = zone.name
                    track.zone_entry_time = track.timestamp
                    track.zone_dwell_seconds = 0.0

                    # Track repeated entry count
                    if t_id not in self._track_zone_entry_count:
                        self._track_zone_entry_count[t_id] = {}
                    entry_count = self._track_zone_entry_count[t_id].get(z_id, 0) + 1
                    self._track_zone_entry_count[t_id][z_id] = entry_count

                    # Track first entry for persistence escalation
                    if t_id not in self._track_zone_first_entry:
                        self._track_zone_first_entry[t_id] = {}
                    if z_id not in self._track_zone_first_entry[t_id]:
                        self._track_zone_first_entry[t_id][z_id] = track.timestamp

                    narrative = f"{track.object_class.upper()} #{t_id} entered {zone.name} moving {heading}."
                    is_restricted = zone.severity in (ZoneSeverity.RESTRICTED, ZoneSeverity.CRITICAL)

                    # Check for repeated entry
                    entry_count = self._track_zone_entry_count.get(t_id, {}).get(z_id, 1)
                    if entry_count > 1:
                        narrative = (
                            f"{track.object_class.upper()} #{t_id} re-entered {zone.name} "
                            f"(entry #{entry_count}) moving {heading}."
                        )

                    t_score, t_level, t_reasons = compute_threat_score(
                        has_restricted_intrusion=is_restricted,
                        has_tripwire_breach=False,
                        has_loitering=False,
                        has_night_movement=is_night,
                        has_multiple_unauthorized=len(active_track_ids) > 1 and is_restricted,
                        has_movement_towards_protected=heading_protected,
                    )
                    track.threat_score = t_score

                    ze = ZoneEvent(
                        camera_id=camera_id,
                        track_id=t_id,
                        confidence=track.confidence,
                        source=source,
                        timestamp=track.timestamp,
                        zone_id=zone.zone_id,
                        zone_name=zone.name,
                        zone_severity=zone.severity.value,
                        transition="entered",
                        dwell_duration_seconds=0.0,
                        narrative=narrative,
                        threat_score=t_score,
                        threat_reasons=t_reasons,
                    )
                    zone_events.append(ze)

                    # Generate Security Alert for intrusion into restricted/critical zone
                    if is_restricted:
                        causal_chain = [
                            f"1. {track.object_class.title()} detected (Conf: {int(track.confidence * 100)}%)",
                            f"2. Track #{t_id} established by ByteTrack",
                            f"3. Target entered Restricted Zone '{zone.name}'",
                            f"4. Movement vector: Heading {heading} ({track.speed_description})",
                        ]
                        if is_night:
                            causal_chain.append("5. Night movement detected (22:00–05:00 / Low Light)")
                        if heading_protected:
                            causal_chain.append("6. Directional trajectory heading toward protected assets")
                        causal_chain.append(f"7. Explainable Threat Score evaluated: {t_score} / {t_level}")

                        alert = AlertEvent(
                            camera_id=camera_id,
                            track_id=t_id,
                            confidence=track.confidence,
                            source=source,
                            timestamp=track.timestamp,
                            severity=zone.severity.value.upper(),
                            message=f"SECURITY ALERT: Track {t_id} ({track.object_class}) entered restricted zone '{zone.name}' (Heading {heading})",
                            threat_score=t_score,
                            threat_level=t_level,
                            threat_reasons=t_reasons,
                            causal_chain=causal_chain,
                            heading=heading,
                            speed_description=track.speed_description,
                            target_bbox=list(track.bounding_box) if track.bounding_box else None,
                        )
                        alert_events.append(alert)

                elif not is_inside and was_inside:
                    # STATE TRANSITION: EXITED
                    self._track_zone_state[t_id][z_id] = False
                    entry_time = self._track_zone_entry_time[t_id].pop(z_id, None)
                    dwell_secs = None
                    if entry_time is not None:
                        dwell_secs = max(0.0, (track.timestamp - entry_time).total_seconds())

                    self._track_zone_loiter_alert_time[t_id].pop(z_id, None)
                    track.previous_zone = zone.name
                    track.current_zone = None
                    track.zone_dwell_seconds = 0.0

                    narrative = f"{track.object_class.upper()} #{t_id} exited {zone.name} after {dwell_secs or 0.0:.1f}s."

                    ze = ZoneEvent(
                        camera_id=camera_id,
                        track_id=t_id,
                        confidence=track.confidence,
                        source=source,
                        timestamp=track.timestamp,
                        zone_id=zone.zone_id,
                        zone_name=zone.name,
                        zone_severity=zone.severity.value,
                        transition="exited",
                        dwell_duration_seconds=round(dwell_secs, 2) if dwell_secs is not None else None,
                        narrative=narrative,
                        threat_score=track.threat_score,
                    )
                    zone_events.append(ze)

                elif is_inside and was_inside:
                    # DWELLING: Update dwell clock & evaluate Loitering threshold
                    entry_time = self._track_zone_entry_time[t_id].get(z_id, track.timestamp)
                    dwell_secs = max(0.0, (track.timestamp - entry_time).total_seconds())
                    track.zone_dwell_seconds = dwell_secs
                    track.current_zone = zone.name

                    if zone.loitering_threshold_seconds is not None and zone.loitering_threshold_seconds > 0:
                        if dwell_secs >= zone.loitering_threshold_seconds:
                            last_alert = self._track_zone_loiter_alert_time[t_id].get(z_id)
                            should_alert = False
                            if last_alert is None:
                                should_alert = True
                            elif (track.timestamp - last_alert).total_seconds() >= zone.loitering_debounce_seconds:
                                should_alert = True

                            if should_alert:
                                self._track_zone_loiter_alert_time[t_id][z_id] = track.timestamp
                                narrative = f"{track.object_class.upper()} #{t_id} loitering in {zone.name} for {dwell_secs:.1f}s."

                                t_score, t_level, t_reasons = compute_threat_score(
                                    has_restricted_intrusion=zone.severity in (ZoneSeverity.RESTRICTED, ZoneSeverity.CRITICAL),
                                    has_tripwire_breach=False,
                                    has_loitering=True,
                                    has_night_movement=is_night,
                                    has_multiple_unauthorized=len(active_track_ids) > 1,
                                    has_movement_towards_protected=heading_protected,
                                )
                                track.threat_score = t_score

                                ze = ZoneEvent(
                                    camera_id=camera_id,
                                    track_id=t_id,
                                    confidence=track.confidence,
                                    source=source,
                                    timestamp=track.timestamp,
                                    zone_id=zone.zone_id,
                                    zone_name=zone.name,
                                    zone_severity=zone.severity.value,
                                    transition="loitering",
                                    dwell_duration_seconds=round(dwell_secs, 2),
                                    narrative=narrative,
                                    threat_score=t_score,
                                    threat_reasons=t_reasons,
                                )
                                zone_events.append(ze)

                                causal_chain = [
                                    f"1. {track.object_class.title()} detected in sector",
                                    f"2. Track #{t_id} continuously observed in '{zone.name}'",
                                    f"3. Dwell duration exceeded security limit ({dwell_secs:.1f}s >= {zone.loitering_threshold_seconds}s)",
                                ]
                                if is_night:
                                    causal_chain.append("4. Night surveillance period active")
                                causal_chain.append(f"5. Loitering Threat Score evaluated: {t_score} / {t_level}")

                                alert = AlertEvent(
                                    camera_id=camera_id,
                                    track_id=t_id,
                                    confidence=track.confidence,
                                    source=source,
                                    timestamp=track.timestamp,
                                    severity=zone.severity.value.upper(),
                                    message=(
                                        f"LOITERING ALERT: Track {t_id} ({track.object_class}) dwelling in zone "
                                        f"'{zone.name}' for {dwell_secs:.1f}s (threshold: {zone.loitering_threshold_seconds}s)"
                                    ),
                                    threat_score=t_score,
                                    threat_level=t_level,
                                    threat_reasons=t_reasons,
                                    causal_chain=causal_chain,
                                    heading=heading,
                                    speed_description=track.speed_description,
                                    target_bbox=list(track.bounding_box) if track.bounding_box else None,
                                )
                                alert_events.append(alert)

                    # Persistence escalation: long dwell beyond persistence_threshold
                    if zone.persistence_threshold_seconds and dwell_secs >= zone.persistence_threshold_seconds:
                        last_persist = self._track_zone_persistence_alert_time.get(t_id, {}).get(z_id)
                        should_escalate = False
                        if last_persist is None:
                            should_escalate = True
                        elif (track.timestamp - last_persist).total_seconds() >= zone.loitering_debounce_seconds:
                            should_escalate = True

                        if should_escalate:
                            if t_id not in self._track_zone_persistence_alert_time:
                                self._track_zone_persistence_alert_time[t_id] = {}
                            self._track_zone_persistence_alert_time[t_id][z_id] = track.timestamp
                            entry_count = self._track_zone_entry_count.get(t_id, {}).get(z_id, 1)
                            narrative = (
                                f"{track.object_class.upper()} #{t_id} persistent presence in {zone.name} "
                                f"for {dwell_secs:.1f}s (entry #{entry_count})."
                            )
                            t_score, t_level, t_reasons = compute_threat_score(
                                has_restricted_intrusion=zone.severity in (ZoneSeverity.RESTRICTED, ZoneSeverity.CRITICAL),
                                has_tripwire_breach=False,
                                has_loitering=True,
                                has_night_movement=is_night,
                                has_multiple_unauthorized=len(active_track_ids) > 1,
                                has_movement_towards_protected=heading_protected,
                            )
                            track.threat_score = t_score
                            ze = ZoneEvent(
                                camera_id=camera_id,
                                track_id=t_id,
                                confidence=track.confidence,
                                source=source,
                                timestamp=track.timestamp,
                                zone_id=zone.zone_id,
                                zone_name=zone.name,
                                zone_severity=zone.severity.value,
                                transition="persistence",
                                dwell_duration_seconds=round(dwell_secs, 2),
                                narrative=narrative,
                                threat_score=t_score,
                                threat_reasons=t_reasons,
                            )
                            zone_events.append(ze)

            # 2. Evaluate Virtual Boundaries (Directional Line crossing)
            if prev_pos is not None:
                for b_id, boundary in self.boundaries.items():
                    if not boundary.is_active:
                        continue
                    if boundary.target_classes and track.object_class not in boundary.target_classes:
                        continue

                    crossing_dir = boundary.check_crossing(prev_pos, curr_pos)
                    if crossing_dir is not None:
                        # Debounce check per track and boundary
                        if t_id not in self._track_boundary_alert_time:
                            self._track_boundary_alert_time[t_id] = {}
                        last_alert_time = self._track_boundary_alert_time[t_id].get(b_id)
                        if last_alert_time is not None:
                            elapsed = (track.timestamp - last_alert_time).total_seconds()
                            if elapsed < boundary.debounce_seconds:
                                continue
                        self._track_boundary_alert_time[t_id][b_id] = track.timestamp

                        crossing_label = crossing_dir if crossing_dir in ("NORTH", "SOUTH", "EAST", "WEST", "LEFT_TO_RIGHT", "RIGHT_TO_LEFT", "INWARD", "OUTWARD") else ("A -> B" if crossing_dir == "inbound" else "B -> A")
                        narrative = f"{track.object_class.upper()} #{t_id} breached tripwire '{boundary.name}' in direction {crossing_label}."

                        t_score, t_level, t_reasons = compute_threat_score(
                            has_restricted_intrusion=False,
                            has_tripwire_breach=True,
                            has_loitering=False,
                            has_night_movement=is_night,
                            has_multiple_unauthorized=len(active_track_ids) > 1,
                            has_movement_towards_protected=heading_protected,
                        )
                        track.threat_score = t_score

                        ze = ZoneEvent(
                            camera_id=camera_id,
                            track_id=t_id,
                            confidence=track.confidence,
                            source=source,
                            timestamp=track.timestamp,
                            zone_id=boundary.boundary_id,
                            zone_name=boundary.name,
                            zone_severity=boundary.severity.value,
                            transition="crossed",
                            crossing_direction=crossing_label,
                            narrative=narrative,
                            threat_score=t_score,
                            threat_reasons=t_reasons,
                        )
                        zone_events.append(ze)

                        causal_chain = [
                            f"1. {track.object_class.title()} detected on perimeter",
                            f"2. Persistent Track #{t_id} movement tracked across frames",
                            f"3. Virtual tripwire '{boundary.name}' breached ({crossing_label})",
                            f"4. Movement vector: Heading {heading} ({track.speed_description})",
                        ]
                        if is_night:
                            causal_chain.append("5. Night intrusion condition triggered")
                        if heading_protected:
                            causal_chain.append("6. Directional vector aimed at internal defense perimeter")
                        causal_chain.append(f"7. Border Breach Threat Score evaluated: {t_score} / {t_level}")

                        alert = AlertEvent(
                            camera_id=camera_id,
                            track_id=t_id,
                            confidence=track.confidence,
                            source=source,
                            timestamp=track.timestamp,
                            severity=boundary.severity.value.upper(),
                            message=f"BORDER BREACH: Track {t_id} ({track.object_class}) crossed virtual boundary '{boundary.name}' ({crossing_label})",
                            threat_score=t_score,
                            threat_level=t_level,
                            threat_reasons=t_reasons,
                            causal_chain=causal_chain,
                            heading=heading,
                            speed_description=track.speed_description,
                            target_bbox=list(track.bounding_box) if track.bounding_box else None,
                        )
                        alert_events.append(alert)

            # Update previous position
            self._track_prev_positions[t_id] = curr_pos

        # Cleanup tracks that are no longer active
        dormant_ids = [tid for tid in list(self._track_prev_positions.keys()) if tid not in active_track_ids]
        for tid in dormant_ids:
            if tid in self._track_zone_state:
                for z_id, was_in in self._track_zone_state[tid].items():
                    if was_in and z_id in self.zones:
                        z = self.zones[z_id]
                        entry_time = self._track_zone_entry_time.get(tid, {}).pop(z_id, None)
                        ze = ZoneEvent(
                            camera_id=camera_id,
                            track_id=tid,
                            source=source,
                            zone_id=z.zone_id,
                            zone_name=z.name,
                            zone_severity=z.severity.value,
                            transition="exited",
                            dwell_duration_seconds=0.0,
                            narrative=f"Track #{tid} disappeared/exited {z.name}.",
                        )
                        zone_events.append(ze)
                del self._track_zone_state[tid]
            if tid in self._track_zone_entry_time:
                del self._track_zone_entry_time[tid]
            if tid in self._track_zone_loiter_alert_time:
                del self._track_zone_loiter_alert_time[tid]
            if tid in self._track_boundary_alert_time:
                del self._track_boundary_alert_time[tid]
            self._track_operator_alert_time.pop(tid, None)
            self._track_operator_last_severity.pop(tid, None)
            self._track_zone_entry_count.pop(tid, None)
            self._track_zone_first_entry.pop(tid, None)
            self._track_zone_persistence_alert_time.pop(tid, None)
            del self._track_prev_positions[tid]

        # Preserve every zone event for the forensic timeline, but emit at most
        # one operator alert per track in the cooldown window. If a target
        # simultaneously enters a zone and crosses a tripwire, the CRITICAL
        # border-breach alert wins over the lower-severity zone alert.
        severity_rank = {"CRITICAL": 3, "RESTRICTED": 2, "NORMAL": 1}
        selected_alerts: Dict[str, AlertEvent] = {}
        for alert in alert_events:
            previous = selected_alerts.get(str(alert.track_id))
            if previous is None or severity_rank.get(alert.severity.upper(), 0) > severity_rank.get(previous.severity.upper(), 0):
                selected_alerts[str(alert.track_id)] = alert

        operator_alerts: List[AlertEvent] = []
        for track_id, alert in selected_alerts.items():
            last_alert = self._track_operator_alert_time.get(track_id)
            current_rank = severity_rank.get(alert.severity.upper(), 0)
            last_rank = self._track_operator_last_severity.get(track_id, 0)
            is_escalation = current_rank > last_rank
            if last_alert is None or is_escalation or (alert.timestamp - last_alert).total_seconds() >= self.operator_alert_cooldown_seconds:
                self._track_operator_alert_time[track_id] = alert.timestamp
                self._track_operator_last_severity[track_id] = current_rank
                operator_alerts.append(alert)

        return zone_events, operator_alerts

    def get_zone_occupancy(self) -> Dict[str, List[dict]]:
        """
        Return current zone occupancy state for all zones.
        Maps zone_id -> list of tracks currently inside, with dwell times.
        """
        result: Dict[str, List[dict]] = {}
        for t_id, zone_states in self._track_zone_state.items():
            for z_id, is_inside in zone_states.items():
                if is_inside and z_id in self.zones:
                    zone = self.zones[z_id]
                    entry_time = self._track_zone_entry_time.get(t_id, {}).get(z_id)
                    dwell = 0.0
                    if entry_time:
                        dwell = max(0.0, (datetime.now(timezone.utc) - entry_time).total_seconds())
                    entry_count = self._track_zone_entry_count.get(t_id, {}).get(z_id, 1)
                    if z_id not in result:
                        result[z_id] = []
                    result[z_id].append({
                        "track_id": t_id,
                        "zone_name": zone.name,
                        "zone_severity": zone.severity.value,
                        "dwell_seconds": round(dwell, 1),
                        "entry_count": entry_count,
                    })
        return result


global_zone_monitor = ZoneMonitor()


def get_zone_monitor() -> ZoneMonitor:
    return global_zone_monitor
