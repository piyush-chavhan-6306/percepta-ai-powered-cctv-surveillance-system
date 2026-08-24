"""
Border Intelligence Event Schema Module.
Defines all typed Pydantic event models with validated serialization and deserialization.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class EventType(str, Enum):
    DETECTION = "DETECTION"
    TRACKING = "TRACKING"
    ZONE = "ZONE"
    RISK = "RISK"
    EVIDENCE = "EVIDENCE"
    ALERT = "ALERT"
    INCIDENT = "INCIDENT"
    HANDOFF = "HANDOFF"   # P1 Cross-camera
    SYSTEM = "SYSTEM"     # Failure, recovery, degradation


class SourceType(str, Enum):
    VIDEO_FILE = "video_file"
    SIMULATION = "simulation"
    RADAR_SIM = "radar_sim"
    RF_SIM = "rf_sim"
    THERMAL_SIM = "thermal_sim"
    UNAVAILABLE = "unavailable"


class BaseEvent(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    event_type: EventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    camera_id: str
    track_id: Optional[str] = None
    incident_id: Optional[str] = None
    confidence: Optional[float] = None
    source: SourceType = SourceType.VIDEO_FILE


class DetectionEvent(BaseEvent):
    event_type: EventType = EventType.DETECTION
    object_class: str  # e.g., "person", "vehicle", "drone"
    bounding_box: List[float]  # [x1, y1, x2, y2]
    frame_number: int


class TrackingEvent(BaseEvent):
    event_type: EventType = EventType.TRACKING
    lifecycle: str  # "created", "updated", "lost", "recovered", "terminated"
    position: List[float]  # [cx, cy]
    velocity: List[float]  # [dx, dy]
    object_class: Optional[str] = None
    bounding_box: Optional[List[float]] = None  # [x1, y1, x2, y2]
    frame_number: Optional[int] = None
    speed: Optional[float] = None  # pixels/frame
    direction: Optional[float] = None  # degrees (0-360)


class ZoneEvent(BaseEvent):
    event_type: EventType = EventType.ZONE
    zone_id: str
    zone_name: str
    zone_severity: str  # "warning", "restricted", "critical"
    transition: str  # "entered", "exited", "dwelling", "crossed", "loitering"
    dwell_duration_seconds: Optional[float] = None


class RiskEvent(BaseEvent):
    event_type: EventType = EventType.RISK
    risk_level: str  # "low", "medium", "high", "critical"
    reasons: List[str]  # Explainable human-readable rule list


class EvidenceEvent(BaseEvent):
    event_type: EventType = EventType.EVIDENCE
    frame_path: str
    frame_number: int
    trigger_reason: str
    frame_type: str = "trigger"  # "pre_event", "trigger", "post_event"


class AlertEvent(BaseEvent):
    event_type: EventType = EventType.ALERT
    alert_id: UUID = Field(default_factory=uuid4)
    severity: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    message: str
    is_acknowledged: bool = False


class IncidentEvent(BaseEvent):
    event_type: EventType = EventType.INCIDENT
    lifecycle: str  # "opened", "updated", "closed"
    event_ids: List[UUID] = Field(default_factory=list)


class SystemEvent(BaseEvent):
    event_type: EventType = EventType.SYSTEM
    subtype: str  # "camera_unavailable", "camera_recovered", "model_error",
                  # "pipeline_degraded", "pipeline_recovered", "evidence_unavailable", "database_error"
    details: str


class CameraHandoffEvent(BaseEvent):  # P1
    event_type: EventType = EventType.HANDOFF
    from_camera_id: str
    to_camera_id: str
    association_score: float
    association_status: str  # "likely", "ambiguous", "rejected"
