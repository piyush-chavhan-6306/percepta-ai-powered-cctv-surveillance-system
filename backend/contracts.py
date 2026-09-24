"""
PERCEPTA Defense — Interface Contracts.

Defines the normalized data shapes that flow between pipeline stages.
These are plain dataclasses — not ORM models — so they can be used
in-memory without a database session.

Pipeline flow:
    DetectionResult → TrackResult → EventContract → IncidentContract → AlertContract
                                                                 ↓
                                                          EvidenceContract
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ─────────────────────────────────────────────
# Enumerations
# ─────────────────────────────────────────────

class EntityType(str, Enum):
    PERSON = "person"
    VEHICLE = "vehicle"
    ANIMAL = "animal"
    UNKNOWN = "unknown"


class DetectorSource(str, Enum):
    YOLOV8N = "yolov8n"
    YOLOV8N_PLATE = "plate_yolov8n"
    YUNET = "yunet"
    WEAPON = "weapon"
    THERMAL = "thermal"


class EventCategory(str, Enum):
    INTRUSION = "INTRUSION"
    LOITERING = "LOITERING"
    ZONE_CROSSING = "ZONE_CROSSING"
    TRACK_APPEARANCE = "TRACK_APPEARANCE"
    TRACK_DISAPPEARANCE = "TRACK_DISAPPEARANCE"
    FACE_DETECTED = "FACE_DETECTED"
    PLATE_DETECTED = "PLATE_DETECTED"
    WEAPON_DETECTED = "WEAPON_DETECTED"
    CAMERA_OFFLINE = "CAMERA_OFFLINE"
    CAMERA_ONLINE = "CAMERA_ONLINE"
    SYSTEM_ERROR = "SYSTEM_ERROR"


class IncidentStatus(str, Enum):
    DETECTED = "DETECTED"
    CONFIRMED = "CONFIRMED"
    ESCALATED = "ESCALATED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    FALSE_POSITIVE = "FALSE_POSITIVE"


class Severity(str, Enum):
    NORMAL = "NORMAL"
    ELEVATED = "ELEVATED"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertSeverity(str, Enum):
    INFORMATIONAL = "INFORMATIONAL"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class EvidenceType(str, Enum):
    FACE_CROP = "face_crop"
    PLATE_CROP = "plate_crop"
    FULL_SCENE = "full_scene"
    TARGET_CROP = "target_crop"
    WEAPON_CROP = "weapon_crop"


# ─────────────────────────────────────────────
# Bounding Box
# ─────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class BBox:
    """Axis-aligned bounding box in pixel coordinates."""
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    @property
    def area(self) -> float:
        return max(self.width, 0.0) * max(self.height, 0.0)

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2.0, (self.y1 + self.y2) / 2.0)

    def to_dict(self) -> dict[str, float]:
        return {"x1": self.x1, "y1": self.y1, "x2": self.x2, "y2": self.y2}

    @classmethod
    def from_dict(cls, d: dict[str, float]) -> BBox:
        return cls(x1=d["x1"], y1=d["y1"], x2=d["x2"], y2=d["y2"])


# ─────────────────────────────────────────────
# Detection Result (output of detector)
# ─────────────────────────────────────────────

@dataclass(slots=True)
class DetectionResult:
    """Single detection from any detector (YOLO, YuNet, weapon, etc.)."""
    class_name: str
    confidence: float
    bbox: BBox
    detector_source: DetectorSource
    frame_number: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


# ─────────────────────────────────────────────
# Track Result (output of tracker)
# ─────────────────────────────────────────────

@dataclass(slots=True)
class TrackResult:
    """A tracked object assignment from ByteTrack or similar."""
    local_track_id: str
    class_name: str
    bbox: BBox
    confidence: float
    frame_number: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    velocity: tuple[float, float] | None = None
    trajectory: list[tuple[float, float]] = field(default_factory=list)
    reid_embedding: list[float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ─────────────────────────────────────────────
# Event Contract (output of event builder)
# ─────────────────────────────────────────────

@dataclass(slots=True)
class EventContract:
    """A normalized event ready for persistence and publication."""
    event_id: str
    event_type: EventCategory
    camera_id: str
    timestamp: datetime
    local_track_id: str | None = None
    global_entity_id: str | None = None
    session_id: str | None = None
    zone_id: str | None = None
    incident_id: str | None = None
    entity_type: EntityType | None = None
    confidence: float | None = None
    source: str = "pipeline"
    metadata: dict[str, Any] = field(default_factory=dict)
    evidence_id: str | None = None


# ─────────────────────────────────────────────
# Incident Contract (output of incident engine)
# ─────────────────────────────────────────────

@dataclass(slots=True)
class IncidentContract:
    """A grouped incident ready for operator consumption."""
    incident_id: str
    incident_type: str
    status: IncidentStatus
    severity: Severity
    created_at: datetime
    primary_camera_id: str | None = None
    primary_entity_id: str | None = None
    zone_id: str | None = None
    entry_time: datetime | None = None
    last_seen: datetime | None = None
    exit_time: datetime | None = None
    duration_seconds: float | None = None
    peak_threat: float = 0.0
    current_threat: float = 0.0
    reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ─────────────────────────────────────────────
# Alert Contract (output of alert engine)
# ─────────────────────────────────────────────

@dataclass(slots=True)
class AlertContract:
    """An operator-facing alert — one per incident."""
    alert_id: str
    incident_id: str
    operator_severity: AlertSeverity
    operator_status: AlertStatus
    message: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ─────────────────────────────────────────────
# Evidence Contract (output of evidence engine)
# ─────────────────────────────────────────────

@dataclass(slots=True)
class EvidenceContract:
    """Target-specific evidence tied to an incident."""
    evidence_id: str
    incident_id: str
    event_id: str | None = None
    global_entity_id: str | None = None
    local_track_id: str | None = None
    camera_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    evidence_type: EvidenceType = EvidenceType.FULL_SCENE
    source_frame_number: int | None = None
    target_bbox: BBox | None = None
    target_crop_path: str | None = None
    full_scene_path: str | None = None
    confidence: float | None = None
    quality: float | None = None
    reason: str | None = None
    sha256_hash: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ─────────────────────────────────────────────
# Cross-Camera Transition
# ─────────────────────────────────────────────

@dataclass(slots=True)
class CameraTransitionRecord:
    """A cross-camera entity association."""
    transition_id: str
    global_entity_id: str
    from_camera_id: str
    from_local_track_id: str
    to_camera_id: str
    to_local_track_id: str
    association_confidence: float
    transition_time: datetime
    association_signals: dict[str, Any] = field(default_factory=dict)


# ─────────────────────────────────────────────
# Specialized Observations
# ─────────────────────────────────────────────

@dataclass(slots=True)
class FaceObservationContract:
    """Face detection result ready for persistence."""
    camera_id: str
    confidence: float
    timestamp: datetime
    local_track_id: str | None = None
    global_entity_id: str | None = None
    frame_number: int | None = None
    face_bbox: BBox | None = None
    face_crop_path: str | None = None
    quality_score: float | None = None
    landmarks: list[list[float]] | None = None


@dataclass(slots=True)
class PlateObservationContract:
    """ANPR plate result ready for persistence."""
    camera_id: str
    timestamp: datetime
    local_track_id: str | None = None
    global_entity_id: str | None = None
    frame_number: int | None = None
    plate_text: str | None = None
    plate_confidence: float | None = None
    plate_uncertain: bool = True
    plate_bbox: BBox | None = None
    plate_crop_path: str | None = None
    vehicle_class: str | None = None
    consensus_hits: int | None = None


@dataclass(slots=True)
class WeaponObservationContract:
    """Weapon detection result ready for persistence."""
    camera_id: str
    confidence: float
    timestamp: datetime
    local_track_id: str | None = None
    global_entity_id: str | None = None
    frame_number: int | None = None
    weapon_class: str | None = None
    weapon_bbox: BBox | None = None
    crop_path: str | None = None
    model_source: str | None = None


# ─────────────────────────────────────────────
# Threat Assessment
# ─────────────────────────────────────────────

@dataclass(slots=True)
class ThreatAssessmentContract:
    """Explainable threat score for an incident."""
    assessment_id: str
    incident_id: str
    score: float
    severity: Severity
    factors: list[dict[str, Any]] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source_event_id: str | None = None
    explanation: str | None = None
