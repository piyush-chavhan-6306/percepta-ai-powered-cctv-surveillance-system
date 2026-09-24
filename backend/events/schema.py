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
    ANPR = "ANPR"         # Modular License Plate Prototype
    FACE = "FACE"         # Face Detection Analytics (Non-biometric)
    CORRELATION = "CORRELATION" # Multi-Camera Spatial-Temporal Correlation


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
    # Cross-camera person identity assigned by the Re-ID Global Identity Manager
    # (backend/tracking/reid_manager.py). None for vehicles / unconfirmed
    # persons / when Re-ID is disabled. Person appearance Re-ID only — NOT face
    # recognition; the field name is deliberately explicit about that.
    global_person_id: Optional[str] = None
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
    cardinal_heading: Optional[str] = None  # e.g. "NE", "S", "STATIONARY"
    speed_description: Optional[str] = None  # e.g. "Moving (~2.4 m/s est)" or "Stationary"
    current_zone: Optional[str] = None
    previous_zone: Optional[str] = None
    zone_dwell_seconds: Optional[float] = None
    movement_state: Optional[str] = None  # "APPROACHING_RESTRICTED", "RECEDING", "CROSSING", "LOITERING"
    heading_towards_protected: Optional[bool] = False
    is_night_movement: Optional[bool] = False
    threat_score: Optional[float] = None


class ZoneEvent(BaseEvent):
    event_type: EventType = EventType.ZONE
    zone_id: str
    zone_name: str
    zone_severity: str  # "warning", "restricted", "critical"
    transition: str  # "entered", "exited", "dwelling", "crossed", "loitering", "persistence"
    dwell_duration_seconds: Optional[float] = None
    crossing_direction: Optional[str] = None  # "inbound", "outbound", "A_TO_B", "B_TO_A"
    narrative: Optional[str] = None  # e.g., "PERSON #27 entered Restricted Zone A and moved NE toward Checkpoint B."
    threat_score: Optional[float] = None
    threat_reasons: Optional[List[str]] = None


class RiskEvent(BaseEvent):
    event_type: EventType = EventType.RISK
    risk_level: str  # "low", "medium", "high", "critical"
    threat_score: float = 0.0
    reasons: List[str] = Field(default_factory=list)  # Explainable human-readable rule list


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
    threat_score: Optional[float] = None
    threat_level: Optional[str] = None  # "NORMAL", "ELEVATED", "HIGH", "CRITICAL"
    threat_reasons: Optional[List[str]] = None  # ["+35 Restricted Zone Intrusion", "+30 Tripwire Breach", ...]
    causal_chain: Optional[List[str]] = None   # Step-by-step why this alert was generated
    evidence_snapshot_uri: Optional[str] = None
    face_snapshot_uri: Optional[str] = None
    anpr_snapshot_uri: Optional[str] = None
    plate_number: Optional[str] = None          # OCR reading, may be empty when unreadable
    plate_confidence: Optional[float] = None    # mean CTC character confidence
    plate_uncertain: bool = False               # True when below acceptance gate
    face_confidence: Optional[float] = None     # YuNet detection confidence
    best_frame_number: Optional[int] = None
    modality: str = "STANDARD"  # "STANDARD", "IR_NIGHT", "THERMAL"
    timeline_offset_sec: Optional[float] = None
    heading: Optional[str] = None
    speed_description: Optional[str] = None
    target_bbox: Optional[List[float]] = None


class IncidentEvent(BaseEvent):
    event_type: EventType = EventType.INCIDENT
    lifecycle: str  # "opened", "updated", "closed"
    event_ids: List[UUID] = Field(default_factory=list)


class SystemEvent(BaseEvent):
    event_type: EventType = EventType.SYSTEM
    subtype: str  # "camera_unavailable", "camera_recovered", "model_error",
                  # "pipeline_degraded", "pipeline_recovered", "evidence_unavailable", "database_error", "camera_health_warning"
    details: str


class CameraHandoffEvent(BaseEvent):  # P1
    event_type: EventType = EventType.HANDOFF
    from_camera_id: str
    to_camera_id: str
    association_score: float
    association_status: str  # "likely", "ambiguous", "rejected"


class ANPREvent(BaseEvent):
    event_type: EventType = EventType.ANPR
    plate_number: str
    vehicle_class: str
    detection_confidence: float
    is_verified_format: bool = True
    evidence_snapshot_uri: Optional[str] = None
    notes: Optional[str] = "Modular ANPR Prototype (SIH26187 Alignment)"


class FaceAnalyticsEvent(BaseEvent):
    event_type: EventType = EventType.FACE
    face_detected: bool = True
    face_bounding_box: List[float]  # [x1, y1, x2, y2]
    identity_claim: str = "UNIDENTIFIED (Detection Only — Non-Biometric)"
    evidence_snapshot_uri: Optional[str] = None


class CorrelationEvent(BaseEvent):
    event_type: EventType = EventType.CORRELATION
    source_camera: str
    target_camera: str
    source_zone: Optional[str] = None
    target_zone: Optional[str] = None
    time_delta_seconds: float
    correlation_confidence: float
    correlation_label: str = "Probable cross-camera event correlation"
    narrative: str
