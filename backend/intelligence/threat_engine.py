"""
Border Intelligence Real-Time Threat Assessment & Sector Threat Index Engine.
Computes deterministic, explainable DEFCON threat levels from active surveillance events.
"""
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.events.store import EventStore, get_event_store


class ThreatLevel(str, Enum):
    DEFCON_GREEN = "DEFCON_GREEN"      # Normal / Low Risk (0 - 20)
    DEFCON_YELLOW = "DEFCON_YELLOW"    # Elevated Risk (21 - 50)
    DEFCON_ORANGE = "DEFCON_ORANGE"    # High Alert (51 - 80)
    DEFCON_RED = "DEFCON_RED"          # Critical Breach / Emergency (81 - 100)


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

        # 1. Fetch recent alerts from SQLite WAL store
        alerts = await self.store.get_alerts(camera_id=camera_id, limit=50)

        # Filter alerts within lookback window
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
        )

        critical_count = 0
        restricted_count = 0
        warning_count = 0
        loiter_count = 0
        contributing_factors = []

        for a in recent_alerts:
            sev = str(a.get("payload", "")).upper() or str(a.get("source", "")).upper()
            msg = str(a.get("payload", ""))
            if "CRITICAL" in sev or "BORDER BREACH" in msg or "crossed" in msg.lower():
                critical_count += 1
            elif "RESTRICTED" in sev or "entered restricted" in msg.lower():
                restricted_count += 1
            elif "LOITER" in msg.upper() or "dwelling" in msg.lower():
                loiter_count += 1
            else:
                warning_count += 1

        active_track_ids = set()
        for e in recent_events:
            if e.get("track_id"):
                active_track_ids.add(e["track_id"])
            if e.get("event_type") == "ZONE" and "loiter" in str(e.get("payload", "")).lower():
                loiter_count += 1

        # 3. Calculate mathematical score
        raw_score = (
            (critical_count * 35.0)
            + (restricted_count * 20.0)
            + (loiter_count * 15.0)
            + (warning_count * 5.0)
            + (min(len(active_track_ids), 10) * 2.0)
        )
        score = min(100.0, max(0.0, raw_score))

        # 4. Map to DEFCON Threat Level
        if score >= 80.0:
            level = ThreatLevel.DEFCON_RED
            action = "CRITICAL: Immediate Quick Reaction Force (QRF) dispatch and sector lockdown."
        elif score >= 50.0:
            level = ThreatLevel.DEFCON_ORANGE
            action = "HIGH: Alert sector commander, zoom PTZ cameras to breach vectors, ready patrol units."
        elif score >= 20.0:
            level = ThreatLevel.DEFCON_YELLOW
            action = "ELEVATED: Maintain focused surveillance on active tracks, monitor dwell timers."
        else:
            level = ThreatLevel.DEFCON_GREEN
            action = "NORMAL: Standard autonomous perimeter monitoring active."

        # 5. Build explainable factors
        if critical_count > 0:
            contributing_factors.append(f"{critical_count} critical boundary crossing/breach events detected.")
        if restricted_count > 0:
            contributing_factors.append(f"{restricted_count} unauthorized restricted zone entries.")
        if loiter_count > 0:
            contributing_factors.append(f"{loiter_count} targets dwelling beyond security threshold.")
        if len(active_track_ids) > 0:
            contributing_factors.append(f"{len(active_track_ids)} active persistent targets in sector.")
        if not contributing_factors:
            contributing_factors.append("Zero anomalous events detected in current time window.")

        return ThreatAssessment(
            timestamp=now,
            camera_id=camera_id,
            threat_level=level,
            threat_score=round(score, 1),
            active_breaches=critical_count + restricted_count,
            active_loiterers=loiter_count,
            active_tracks=len(active_track_ids),
            contributing_factors=contributing_factors,
            recommended_action=action,
        )


global_threat_engine = ThreatEngine()


def get_threat_engine() -> ThreatEngine:
    return global_threat_engine
