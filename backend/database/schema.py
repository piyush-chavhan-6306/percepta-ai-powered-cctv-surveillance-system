"""
PERCEPTA Defense — Normalized Database Schema.

Defines all core tables for the intelligence pipeline:
CAMERA → SESSION → DETECTION → LOCAL_TRACK → GLOBAL_ENTITY → EVENT → INCIDENT → ALERT → EVIDENCE

Specialized observations: FACE, PLATE, WEAPON, DRONE
Supporting: ZONE, CAMERA_TRANSITION, THREAT_ASSESSMENT, AI_QUERY
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MetadataMixin:
    """Helper mixin so models with column 'metadata' mapped as 'meta' accept metadata in __init__."""
    def __init__(self, **kwargs):
        if "metadata" in kwargs and "meta" not in kwargs:
            kwargs["meta"] = kwargs.pop("metadata")
        super().__init__(**kwargs)


# ─────────────────────────────────────────────
# CAMERA
# ─────────────────────────────────────────────
class Camera(Base):
    """Camera registry — persisted across restarts."""
    __tablename__ = "cameras"

    camera_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="video_file")
    source_path: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="registered")
    location_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    zone_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    connected_cameras: Mapped[list | None] = mapped_column(JSON, nullable=True)
    expected_direction: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    # Relationships
    sessions = relationship("Session", back_populates="camera", cascade="all, delete-orphan")
    local_tracks = relationship("LocalTrack", back_populates="camera")


# ─────────────────────────────────────────────
# SESSION (processing session per camera)
# ─────────────────────────────────────────────
class Session(Base):
    """A processing session — one per camera start/stop cycle."""
    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    camera_id: Mapped[str] = mapped_column(String(64), ForeignKey("cameras.camera_id"), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    fps: Mapped[float | None] = mapped_column(Float, nullable=True)
    resolution_w: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resolution_h: Mapped[int | None] = mapped_column(Integer, nullable=True)

    camera = relationship("Camera", back_populates="sessions")
    detections = relationship("Detection", back_populates="session")


# ─────────────────────────────────────────────
# ZONE
# ─────────────────────────────────────────────
class Zone(Base):
    """Security zone — persisted, operator-configurable."""
    __tablename__ = "zones"

    zone_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    zone_name: Mapped[str] = mapped_column(String(128), nullable=False)
    zone_type: Mapped[str] = mapped_column(String(32), nullable=False, default="MONITORED")
    severity: Mapped[str] = mapped_column(String(32), nullable=False, default="NORMAL")
    polygon: Mapped[list | None] = mapped_column(JSON, nullable=True)
    camera_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    events = relationship("Event", back_populates="zone")


# ─────────────────────────────────────────────
# DETECTION (raw YOLO output per frame)
# ─────────────────────────────────────────────
class Detection(MetadataMixin, Base):
    """Normalized detection from any detector."""
    __tablename__ = "detections"

    detection_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("sessions.session_id"), nullable=False, index=True)
    camera_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    frame_number: Mapped[int] = mapped_column(Integer, nullable=False)
    class_name: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_x1: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_y1: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_x2: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_y2: Mapped[float] = mapped_column(Float, nullable=False)
    detector_source: Mapped[str] = mapped_column(String(32), nullable=False, default="yolov8n")
    local_track_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    meta: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    session = relationship("Session", back_populates="detections")

    __table_args__ = (
        Index("idx_det_cam_time", "camera_id", "timestamp"),
        Index("idx_det_class", "class_name", "camera_id"),
    )


# ─────────────────────────────────────────────
# LOCAL TRACK (camera-local tracking)
# ─────────────────────────────────────────────
class LocalTrack(Base):
    """Camera-local track — ByteTrack assignment within one camera."""
    __tablename__ = "local_tracks"

    local_track_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    camera_id: Mapped[str] = mapped_column(String(64), ForeignKey("cameras.camera_id"), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    global_entity_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("global_entities.global_entity_id"), nullable=True, index=True)
    class_name: Mapped[str] = mapped_column(String(32), nullable=False)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    frame_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    trajectory: Mapped[list | None] = mapped_column(JSON, nullable=True)
    velocity: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    tracking_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    appearance_embedding: Mapped[bytes | None] = mapped_column(nullable=True)

    camera = relationship("Camera", back_populates="local_tracks")
    global_entity = relationship("GlobalEntity", back_populates="local_tracks")


# ─────────────────────────────────────────────
# GLOBAL ENTITY (cross-camera identity)
# ─────────────────────────────────────────────
class GlobalEntity(MetadataMixin, Base):
    """Persistent global entity — links local tracks across cameras."""
    __tablename__ = "global_entities"

    global_entity_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    display_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_camera_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    current_local_track_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    meta: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    local_tracks = relationship("LocalTrack", back_populates="global_entity")
    transitions = relationship("CameraTransition", back_populates="global_entity", foreign_keys="CameraTransition.global_entity_id")
    events = relationship("Event", back_populates="global_entity")
    incidents = relationship("Incident", back_populates="primary_entity", foreign_keys="Incident.primary_entity_id")


# ─────────────────────────────────────────────
# CAMERA TRANSITION (cross-camera links)
# ─────────────────────────────────────────────
class CameraTransition(Base):
    """Cross-camera entity transition record."""
    __tablename__ = "camera_transitions"

    transition_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    global_entity_id: Mapped[str] = mapped_column(String(36), ForeignKey("global_entities.global_entity_id"), nullable=False, index=True)
    from_camera_id: Mapped[str] = mapped_column(String(64), nullable=False)
    from_local_track_id: Mapped[str] = mapped_column(String(64), nullable=False)
    to_camera_id: Mapped[str] = mapped_column(String(64), nullable=False)
    to_local_track_id: Mapped[str] = mapped_column(String(64), nullable=False)
    association_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    transition_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    association_signals: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    global_entity = relationship("GlobalEntity", back_populates="transitions", foreign_keys=[global_entity_id])


# ─────────────────────────────────────────────
# EVENT (normalized internal event contract)
# ─────────────────────────────────────────────
class Event(MetadataMixin, Base):
    """Normalized event — one row per meaningful observation."""
    __tablename__ = "events"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    camera_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    local_track_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    global_entity_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("global_entities.global_entity_id"), nullable=True, index=True)
    zone_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("zones.zone_id"), nullable=True, index=True)
    incident_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("incidents.incident_id"), nullable=True, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="pipeline")
    meta: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    evidence_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    zone = relationship("Zone", back_populates="events")
    global_entity = relationship("GlobalEntity", back_populates="events")
    incident = relationship("Incident", back_populates="events")

    __table_args__ = (
        Index("idx_event_cam_time", "camera_id", "timestamp"),
        Index("idx_event_type_time", "event_type", "timestamp"),
        Index("idx_event_incident", "incident_id", "timestamp"),
    )

    @property
    def payload(self) -> str:
        import json
        if isinstance(self.meta, dict):
            return json.dumps(self.meta)
        if isinstance(self.meta, str):
            return self.meta
        return "{}"

    @payload.setter
    def payload(self, val: Any) -> None:
        import json
        if isinstance(val, str):
            try:
                self.meta = json.loads(val)
            except Exception:
                self.meta = {"raw": val}
        elif isinstance(val, dict):
            self.meta = val
        else:
            self.meta = {}


# ─────────────────────────────────────────────
# INCIDENT (grouped events → one operator incident)
# ─────────────────────────────────────────────
class Incident(MetadataMixin, Base):
    """Incident — groups related events into one operator-facing entity."""
    __tablename__ = "incidents"

    incident_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    incident_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DETECTED", index=True)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, default="NORMAL")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    entry_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    peak_threat: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    current_threat: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    primary_entity_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("global_entities.global_entity_id"), nullable=True, index=True)
    primary_camera_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    zone_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("zones.zone_id"), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    primary_entity = relationship("GlobalEntity", back_populates="incidents", foreign_keys=[primary_entity_id])
    events = relationship("Event", back_populates="incident")
    alerts = relationship("Alert", back_populates="incident", cascade="all, delete-orphan")
    evidence_items = relationship("Evidence", back_populates="incident", cascade="all, delete-orphan")
    threat_assessments = relationship("ThreatAssessment", back_populates="incident", cascade="all, delete-orphan")


# ─────────────────────────────────────────────
# ALERT (operator-facing, linked to incident)
# ─────────────────────────────────────────────
class Alert(Base):
    """Operator-facing alert — one per incident, updated as threat changes."""
    __tablename__ = "alerts"

    alert_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    incident_id: Mapped[str] = mapped_column(String(36), ForeignKey("incidents.incident_id"), nullable=False, index=True)
    operator_severity: Mapped[str] = mapped_column(String(32), nullable=False, default="INFORMATIONAL")
    operator_status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    incident = relationship("Incident", back_populates="alerts")


# ─────────────────────────────────────────────
# EVIDENCE (target-specific, incident-linked)
# ─────────────────────────────────────────────
class Evidence(MetadataMixin, Base):
    """Evidence — target-specific, linked to incident and event."""
    __tablename__ = "evidence"

    evidence_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    incident_id: Mapped[str] = mapped_column(String(36), ForeignKey("incidents.incident_id"), nullable=False, index=True)
    event_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("events.event_id"), nullable=True)
    global_entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    local_track_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    camera_id: Mapped[str] = mapped_column(String(64), nullable=False)
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_frame_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_bbox: Mapped[list | None] = mapped_column(JSON, nullable=True)
    target_crop_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    full_scene_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    sha256_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    meta: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    incident = relationship("Incident", back_populates="evidence_items")


# ─────────────────────────────────────────────
# THREAT ASSESSMENT (explainable scoring)
# ─────────────────────────────────────────────
class ThreatAssessment(Base):
    """Threat assessment — one per incident state change."""
    __tablename__ = "threat_assessments"

    assessment_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    incident_id: Mapped[str] = mapped_column(String(36), ForeignKey("incidents.incident_id"), nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    factors: Mapped[list | None] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    source_event_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    incident = relationship("Incident", back_populates="threat_assessments")


# ─────────────────────────────────────────────
# FACE OBSERVATION
# ─────────────────────────────────────────────
class FaceObservation(Base):
    """Face detection evidence — associated with a local track."""
    __tablename__ = "face_observations"

    observation_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    camera_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    local_track_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    global_entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    frame_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    face_bbox: Mapped[list | None] = mapped_column(JSON, nullable=True)
    face_crop_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    landmarks: Mapped[list | None] = mapped_column(JSON, nullable=True)
    meta: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)


# ─────────────────────────────────────────────
# PLATE OBSERVATION
# ─────────────────────────────────────────────
class PlateObservation(Base):
    """ANPR/plate detection — associated with a vehicle track."""
    __tablename__ = "plate_observations"

    observation_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    camera_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    local_track_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    global_entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    frame_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    plate_text: Mapped[str | None] = mapped_column(String(32), nullable=True)
    plate_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    plate_uncertain: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    plate_bbox: Mapped[list | None] = mapped_column(JSON, nullable=True)
    plate_crop_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    vehicle_class: Mapped[str | None] = mapped_column(String(32), nullable=True)
    consensus_hits: Mapped[int | None] = mapped_column(Integer, nullable=True)
    meta: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)


# ─────────────────────────────────────────────
# WEAPON OBSERVATION
# ─────────────────────────────────────────────
class WeaponObservation(Base):
    """Weapon detection observation — associated with a track."""
    __tablename__ = "weapon_observations"

    observation_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    camera_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    local_track_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    global_entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    frame_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weapon_class: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    weapon_bbox: Mapped[list | None] = mapped_column(JSON, nullable=True)
    crop_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    model_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    meta: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)


# ─────────────────────────────────────────────
# AI QUERY (Grounded Defense AI audit)
# ─────────────────────────────────────────────
class AIQuery(Base):
    """AI query log — tracks operator queries and responses."""
    __tablename__ = "ai_queries"

    query_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_intent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resolved_entity_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_tier: Mapped[str | None] = mapped_column(String(32), nullable=True)
    facts: Mapped[list | None] = mapped_column(JSON, nullable=True)
    inferences: Mapped[list | None] = mapped_column(JSON, nullable=True)
    unknowns: Mapped[list | None] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    processing_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
