"""
Border Intelligence Real-Time Threat Assessment & Sector Threat Index Engine.
Computes deterministic, explainable DEFCON threat levels from active surveillance events.
"""
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from backend.events.store import EventStore, get_event_store


class ThreatLevel(str, Enum):
    NORMAL = "NORMAL"          # Routine (0 - 29)
    LOW = "LOW"                # Low concern (30 - 49)
    MEDIUM = "MEDIUM"          # Moderate concern (50 - 69)
    HIGH = "HIGH"              # Serious concern (70 - 84)
    CRITICAL = "CRITICAL"      # High-priority breach (85 - 100)
    # Backward compatibility aliases
    DEFCON_GREEN = "NORMAL"
    DEFCON_YELLOW = "LOW"
    DEFCON_ORANGE = "MEDIUM"
    DEFCON_RED = "CRITICAL"
    RESTRICTED = "HIGH"


class ThreatAssessment(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    camera_id: Optional[str] = None
    threat_level: ThreatLevel
    threat_score: float = Field(..., ge=0.0, le=100.0, description="Normalized score 0-100")
    active_breaches: int
    active_loiterers: int
    active_tracks: int
    contributing_factors: List[str]
    recommended_action: str


def compute_threat_score(
    has_restricted_intrusion: bool = False,
    has_tripwire_breach: bool = False,
    has_loitering: bool = False,
    has_night_movement: bool = False,
    has_multiple_unauthorized: bool = False,
    has_movement_towards_protected: bool = False,
    has_weapon_observation: bool = False,
    has_persistence: bool = False,
    has_repeated_entry: bool = False,
    has_cross_camera_tracking: bool = False,
    has_rapid_influx: bool = False,
    has_coordinated_movement: bool = False,
    has_perimeter_closing: bool = False,
) -> Tuple[float, str, List[str]]:
    """
    Deterministic rule-based threat assessment algorithm.
    Explicitly rule-based (zero LLM involved).
    Returns (normalized_score, threat_level_str, reasons_list).
    5-level scoring: NORMAL (0-29), LOW (30-49), MEDIUM (50-69), HIGH (70-84), CRITICAL (85-100).
    """
    raw_score = 0.0
    reasons = []

    if has_restricted_intrusion:
        raw_score += 35.0
        reasons.append("+35 Restricted Zone Intrusion")

    if has_tripwire_breach:
        raw_score += 30.0
        reasons.append("+30 Directional Tripwire Breach")

    if has_weapon_observation:
        raw_score += 35.0
        reasons.append("+35 Weapon-like Object Detected")

    if has_persistence:
        raw_score += 20.0
        reasons.append("+20 Persistent Long-Dwell Presence")

    if has_repeated_entry:
        raw_score += 15.0
        reasons.append("+15 Repeated Zone Re-entry")

    if has_loitering:
        raw_score += 15.0
        reasons.append("+15 Loitering Beyond Threshold")

    if has_night_movement:
        raw_score += 15.0
        reasons.append("+15 Night Movement (22:00-05:00 / Low Light)")

    if has_movement_towards_protected or has_perimeter_closing:
        raw_score += 15.0
        reasons.append("+15 Perimeter Closing Velocity / Movement Vector Toward Protected Area")

    if has_coordinated_movement:
        raw_score += 15.0
        reasons.append("+15 Coordinated Target Movement Vector")

    if has_rapid_influx:
        raw_score += 10.0
        reasons.append("+10 Rapid Target Influx Rate")

    if has_multiple_unauthorized:
        raw_score += 10.0
        reasons.append("+10 Multiple Unauthorized Tracks in Sector")

    if has_cross_camera_tracking:
        raw_score += 5.0
        reasons.append("+5 Cross-Camera Continuity Detected")

    score = min(100.0, max(0.0, raw_score))

    if score >= 65.0:
        level = "CRITICAL"
    elif score >= 50.0:
        level = "HIGH"
    elif score >= 30.0:
        level = "RESTRICTED"
    elif score > 0.0:
        level = "LOW"
    else:
        level = "NORMAL"

    if not reasons:
        reasons.append("Standard autonomous perimeter surveillance (Nominal)")

    return round(score, 1), level, reasons


class ThreatEngine:
    """Evaluates multi-factor surveillance events to compute an objective Sector Threat Index."""

    def __init__(self, store: Optional[EventStore] = None) -> None:
        self.store = store or get_event_store()

    async def evaluate_threat(
        self,
        camera_id: Optional[str] = None,
        lookback_seconds: int = 60,
    ) -> ThreatAssessment:
        """Calculate the real-time threat index over the lookback window."""
        now = datetime.now(timezone.utc)
        since_time = now - timedelta(seconds=lookback_seconds)

        # 1. Fetch recent alerts from SQLite WAL store (camera-specific with sector fallback)
        alerts = await self.store.get_alerts(camera_id=camera_id, limit=50)

        recent_alerts = []
        for a in alerts:
            try:
                t = datetime.fromisoformat(a["timestamp"])
                if t.tzinfo is None:
                    t = t.replace(tzinfo=timezone.utc)
                if t >= since_time:
                    recent_alerts.append(a)
            except Exception:
                recent_alerts.append(a)

        # 2. Fetch recent tracking and zone events
        recent_events = await self.store.get_events(
            since=since_time,
            camera_id=camera_id,
            limit=200,
            newest_first=True,
        )

        has_tripwire = False
        has_restricted = False
        has_loiter = False
        has_night = False
        has_protected = False
        active_track_ids = set()

        # Check hour of day (Night is 22:00 to 05:00)
        hour = now.hour
        if hour >= 22 or hour < 5:
            has_night = True

        critical_count = 0
        restricted_count = 0
        loiter_count = 0

        for a in recent_alerts:
            # EventStore returns the serialized event body as ``parsed_payload``.
            # Reading non-existent top-level payload/severity fields silently made
            # real alerts look empty, leaving the dashboard threat meter normal.
            payload = a.get("parsed_payload") or {}
            msg = " ".join(
                str(payload.get(key) or a.get(key) or "")
                for key in ("message", "narrative", "transition", "zone_name", "zone_severity")
            ).lower()
            sev = str(payload.get("severity") or payload.get("zone_severity") or a.get("severity") or "").upper()
            if "crossed" in msg or "breach" in msg or "tripwire" in msg or "CRITICAL" in sev:
                has_tripwire = True
                critical_count += 1
            if "restricted" in msg or "RESTRICTED" in sev:
                has_restricted = True
                restricted_count += 1
            if "loiter" in msg or "dwelling" in msg:
                has_loiter = True
                loiter_count += 1
            if "night" in msg:
                has_night = True
            if "protected" in msg or "checkpoint" in msg:
                has_protected = True

        for e in recent_events:
            tid = e.get("track_id")
            if tid:
                active_track_ids.add(tid)
            ev_type = e.get("event_type")
            payload = str(e.get("payload", "")).lower()
            if ev_type == "ZONE":
                if "entered" in payload and ("restricted" in payload or "critical" in payload):
                    has_restricted = True
                if "crossed" in payload:
                    has_tripwire = True
                if "loiter" in payload:
                    has_loiter = True
                if "protected" in payload:
                    has_protected = True
            if "night" in payload:
                has_night = True

        # 3. Fetch live active camera tracks from running perception workers
        live_track_count = 0
        live_fast_moving = False
        live_approaching = False
        live_tracks: List[Any] = []
        try:
            from backend.tracking.live_worker import get_worker_registry
            registry = get_worker_registry()
            matching_workers = [w for cid, w in registry._workers.items() if camera_id and cid == camera_id and w.is_running]
            target_workers = matching_workers if matching_workers else [w for w in registry._workers.values() if w.is_running]
            for worker in target_workers:
                cid = worker.camera_id
                if worker.pipeline:
                    tracks = getattr(worker.pipeline, "_last_tracks", [])
                    for t in tracks:
                        live_tracks.append(t)
                        tid = f"{cid}_{t.track_id}"
                        active_track_ids.add(tid)
                        obj_cls = getattr(t, "object_class", "unknown")
                        speed_desc = getattr(t, "speed_description", "")
                        if obj_cls in ("person", "vehicle", "car", "truck", "motorcycle", "bus"):
                            live_track_count += 1
                            if getattr(t, "heading_towards_protected", False):
                                live_approaching = True
                            if "Fast" in speed_desc or "Run" in speed_desc:
                                live_fast_moving = True
        except Exception:
            pass

        # 4. Evaluate Temporal Kinematics (Entity Influx, Coordinated Movement, Perimeter Closing)
        temporal_factors: List[str] = []
        has_rapid_influx = False
        has_coord_motion = False
        has_closing_vel = False
        try:
            from backend.intelligence.temporal_threat import get_temporal_threat_analyzer
            from backend.zones.security_zone import get_zone_monitor
            zm = get_zone_monitor()
            active_bounds = list(zm.boundaries.values())
            active_zones = list(zm.zones.values())
            analyzer = get_temporal_threat_analyzer()
            t_sig = analyzer.analyze_camera(
                camera_id=camera_id or "SECTOR_ALL",
                tracks=live_tracks,
                boundaries=active_bounds,
                zones=active_zones,
            )
            has_rapid_influx = t_sig.has_rapid_influx
            has_coord_motion = t_sig.has_coordinated_movement
            has_closing_vel = t_sig.has_perimeter_closing
            temporal_factors.extend(t_sig.contributing_factors)
        except Exception:
            pass

        if live_approaching or has_closing_vel:
            has_protected = True

        live_base_score = 0.0
        if live_track_count == 1:
            live_base_score = 25.0
        elif live_track_count >= 2:
            live_base_score = 35.0

        if live_fast_moving:
            live_base_score += 15.0

        has_multiple = len(active_track_ids) > 1 and (has_restricted or has_tripwire)

        raw_score = (
            live_base_score
            + (critical_count * 35.0)
            + (restricted_count * 30.0)
            + (loiter_count * 20.0)
            + (15.0 if has_night and live_track_count > 0 else 0.0)
            + (15.0 if has_protected else 0.0)
            + (15.0 if has_coord_motion else 0.0)
            + (10.0 if has_rapid_influx else 0.0)
            + (10.0 if has_multiple else 0.0)
        )
        score = min(100.0, max(0.0, raw_score))

        if score >= 60.0:
            level = ThreatLevel.CRITICAL
        elif score >= 25.0:
            level = ThreatLevel.RESTRICTED
        else:
            level = ThreatLevel.NORMAL

        reasons = []
        if critical_count > 0:
            reasons.append(f"+{critical_count * 35} Directional Tripwire / Boundary Breaches ({critical_count})")
        if restricted_count > 0:
            reasons.append(f"+{restricted_count * 30} Restricted Zone Intrusions ({restricted_count})")
        if loiter_count > 0:
            reasons.append(f"+{loiter_count * 20} Loitering Beyond Threshold ({loiter_count})")
        if live_track_count > 0:
            reasons.append(f"+{int(live_base_score)} Active Tracked Targets in Surveillance Sector ({live_track_count})")
        if live_fast_moving:
            reasons.append("+15 Rapid Target Acceleration Detected")
        if has_night and live_track_count > 0:
            reasons.append("+15 Night Movement (22:00–05:00 / Low Light)")
        if has_protected:
            reasons.append("+15 Movement Vector Toward Protected Area / Boundary Closing")
        if has_coord_motion:
            reasons.append("+15 Coordinated Target Movement Vector")
        if has_rapid_influx:
            reasons.append("+10 Rapid Target Influx Rate")
        if has_multiple:
            reasons.append(f"+10 Multiple Unauthorized Tracks in Sector ({len(active_track_ids)})")

        for tf in temporal_factors:
            if tf not in reasons:
                reasons.append(f"[Temporal Signal] {tf}")

        if not reasons:
            reasons.append("Standard autonomous perimeter surveillance (Nominal)")

        action_map = {
            ThreatLevel.CRITICAL: "CRITICAL: Immediate Quick Reaction Force (QRF) dispatch and sector lockdown.",
            ThreatLevel.RESTRICTED: "RESTRICTED: Alert sector commander, verify zone boundary, ready patrol units.",
            ThreatLevel.NORMAL: "NORMAL: Standard autonomous perimeter monitoring active.",
        }

        return ThreatAssessment(
            timestamp=now,
            camera_id=camera_id,
            threat_level=level,
            threat_score=score,
            active_breaches=(1 if has_tripwire else 0) + (1 if has_restricted else 0),
            active_loiterers=1 if has_loiter else 0,
            active_tracks=len(active_track_ids),
            contributing_factors=reasons,
            recommended_action=action_map.get(level, "Standard monitoring"),
        )


global_threat_engine = ThreatEngine()


def get_threat_engine() -> ThreatEngine:
    return global_threat_engine
