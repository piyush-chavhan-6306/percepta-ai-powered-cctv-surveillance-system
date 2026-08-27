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


class ZoneSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    RESTRICTED = "restricted"
    CRITICAL = "critical"


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
    is_active: bool = True
    target_classes: Optional[Set[str]] = None  # None means all classes
    loitering_threshold_seconds: Optional[float] = None  # None = no loitering check
    loitering_debounce_seconds: float = 30.0  # Cooldown between repeat loitering alerts

    def contains_point(self, point: Tuple[float, float]) -> bool:
        """
        Ray-casting algorithm to test if a 2D point (x, y) is inside the polygon.
        """
        if not self.polygon or len(self.polygon) < 3:
            return False

        x, y = point
        n = len(self.polygon)
        inside = False

        p1x, p1y = self.polygon[0]
        for i in range(1, n + 1):
            p2x, p2y = self.polygon[i % n]
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
    is_active: bool = True
    target_classes: Optional[Set[str]] = None

    def check_crossing(
        self,
        prev_point: Tuple[float, float],
        curr_point: Tuple[float, float],
    ) -> Optional[str]:
        """
        Check if the movement segment (prev_point -> curr_point) crosses this boundary.
        Returns crossing direction ('inbound', 'outbound', 'crossed') or None.
        """
        if prev_point is None or curr_point is None:
            return None

        p0_x, p0_y = prev_point
        p1_x, p1_y = curr_point
        q0_x, q0_y = self.pt1
        q1_x, q1_y = self.pt2

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
            # Determine direction relative to line segment orientation
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
    ) -> None:
        self.zones: Dict[str, SecurityZone] = {z.zone_id: z for z in (zones or [])}
        self.boundaries: Dict[str, VirtualBoundary] = {b.boundary_id: b for b in (boundaries or [])}
        self.event_store = event_store or get_event_store()

        # Track state tracking: {track_id: {zone_id: is_inside}}
        self._track_zone_state: Dict[str, Dict[str, bool]] = {}
        # Track entry timestamps: {track_id: {zone_id: entry_datetime}}
        self._track_zone_entry_time: Dict[str, Dict[str, datetime]] = {}
        # Track last loitering alert timestamps: {track_id: {zone_id: last_alert_datetime}}
        self._track_zone_loiter_alert_time: Dict[str, Dict[str, datetime]] = {}
        # Track previous positions for boundary crossings: {track_id: (x, y)}
        self._track_prev_positions: Dict[str, Tuple[float, float]] = {}

    @classmethod
    def with_shared_definitions(cls, source: "ZoneMonitor") -> "ZoneMonitor":
        """
        Build a monitor that shares `source`'s zone/boundary definitions by
        reference but keeps its own per-track state.

        Live camera workers need both halves of this. Sharing the definition
        dicts means a zone drawn via `/api/zones` (which mutates the global
        monitor) takes effect immediately on every running camera, with no
        re-registration. Keeping state private is what makes multi-camera safe:
        the tracker assigns bare integer track IDs with no camera namespace, and
        occupancy/previous-position state is keyed by that raw ID, so two
        cameras sharing one monitor would overwrite each other's history and
        emit phantom boundary crossings.
        """
        monitor = cls(event_store=source.event_store)
        monitor.zones = source.zones
        monitor.boundaries = source.boundaries
        return monitor

    def add_zone(self, zone: SecurityZone) -> None:
        self.zones[zone.zone_id] = zone

    def add_boundary(self, boundary: VirtualBoundary) -> None:
        self.boundaries[boundary.boundary_id] = boundary

    def reset(self) -> None:
        """Reset internal occupancy states and dwell clocks."""
        self._track_zone_state.clear()
        self._track_zone_entry_time.clear()
        self._track_zone_loiter_alert_time.clear()
        self._track_prev_positions.clear()

    def evaluate_tracks(
        self,
        tracks: List[TrackedObject],
        camera_id: str,
        source: SourceType = SourceType.VIDEO_FILE,
    ) -> Tuple[List[ZoneEvent], List[AlertEvent]]:
        """
        Evaluate current frame tracks against all zones and boundaries.
        Returns (zone_events, alert_events) generated during this frame.
        """
        zone_events: List[ZoneEvent] = []
        alert_events: List[AlertEvent] = []

        active_track_ids = {t.track_id for t in tracks}

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

            # 1. Evaluate Polygon Zones & Loitering
            for z_id, zone in self.zones.items():
                if not zone.is_active:
                    continue
                if zone.target_classes and track.object_class not in zone.target_classes:
                    continue

                is_inside = zone.contains_point(curr_pos) or (
                    hasattr(track, "bbox") and track.bbox and len(track.bbox) >= 4 and zone.contains_point((track.center_x, float(track.bbox[3])))
                )
                was_inside = self._track_zone_state[t_id].get(z_id, False)

                if is_inside and not was_inside:
                    # STATE TRANSITION: ENTERED
                    self._track_zone_state[t_id][z_id] = True
                    self._track_zone_entry_time[t_id][z_id] = track.timestamp

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
                    )
                    zone_events.append(ze)

                    # Generate Security Alert for intrusion into restricted/critical zone
                    if zone.severity in (ZoneSeverity.RESTRICTED, ZoneSeverity.CRITICAL):
                        alert = AlertEvent(
                            camera_id=camera_id,
                            track_id=t_id,
                            confidence=track.confidence,
                            source=source,
                            timestamp=track.timestamp,
                            severity=zone.severity.value.upper(),
                            message=f"SECURITY ALERT: Track {t_id} ({track.object_class}) entered restricted zone '{zone.name}'",
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
                    )
                    zone_events.append(ze)

                elif is_inside and was_inside:
                    # DWELLING: Evaluate Loitering threshold
                    if zone.loitering_threshold_seconds is not None and zone.loitering_threshold_seconds > 0:
                        entry_time = self._track_zone_entry_time[t_id].get(z_id, track.timestamp)
                        dwell_secs = max(0.0, (track.timestamp - entry_time).total_seconds())

                        if dwell_secs >= zone.loitering_threshold_seconds:
                            last_alert = self._track_zone_loiter_alert_time[t_id].get(z_id)
                            should_alert = False
                            if last_alert is None:
                                should_alert = True
                            elif (track.timestamp - last_alert).total_seconds() >= zone.loitering_debounce_seconds:
                                should_alert = True

                            if should_alert:
                                self._track_zone_loiter_alert_time[t_id][z_id] = track.timestamp

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
                                )
                                zone_events.append(ze)

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
                                )
                                alert_events.append(alert)

            # 2. Evaluate Virtual Boundaries (Line crossing)
            if prev_pos is not None:
                for b_id, boundary in self.boundaries.items():
                    if not boundary.is_active:
                        continue
                    if boundary.target_classes and track.object_class not in boundary.target_classes:
                        continue

                    crossing_dir = boundary.check_crossing(prev_pos, curr_pos)
                    if crossing_dir is not None:
                        # BOUNDARY CROSSING EVENT
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
                        )
                        zone_events.append(ze)

                        alert = AlertEvent(
                            camera_id=camera_id,
                            track_id=t_id,
                            confidence=track.confidence,
                            source=source,
                            timestamp=track.timestamp,
                            severity=boundary.severity.value.upper(),
                            message=f"BORDER BREACH: Track {t_id} ({track.object_class}) crossed virtual boundary '{boundary.name}' ({crossing_dir})",
                        )
                        alert_events.append(alert)

            # Update previous position
            self._track_prev_positions[t_id] = curr_pos

        # Cleanup tracks that are no longer active
        dormant_ids = [tid for tid in list(self._track_prev_positions.keys()) if tid not in active_track_ids]
        for tid in dormant_ids:
            # Check if it was inside any zones when it disappeared -> trigger exited
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
                        )
                        zone_events.append(ze)
                del self._track_zone_state[tid]
            if tid in self._track_zone_entry_time:
                del self._track_zone_entry_time[tid]
            if tid in self._track_zone_loiter_alert_time:
                del self._track_zone_loiter_alert_time[tid]
            del self._track_prev_positions[tid]

        return zone_events, alert_events


global_zone_monitor = ZoneMonitor()


def get_zone_monitor() -> ZoneMonitor:
    return global_zone_monitor
