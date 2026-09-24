"""
PERCEPTA Defense — Global Entity Data Models & Schemas.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class EntityStatus(str, Enum):
    ACTIVE = "active"
    LOST = "lost"
    TRANSITIONED = "transitioned"
    TERMINATED = "terminated"


class EntityType(str, Enum):
    PERSON = "person"
    VEHICLE = "vehicle"
    UNKNOWN = "unknown"


class CandidateAssociation(BaseModel):
    """Represents an ambiguous or candidate cross-camera association."""
    candidate_entity_id: str
    candidate_display_id: str
    similarity_score: float
    margin: float = 0.0
    reason: str = ""
    camera_id: str = ""
    local_track_id: str = ""
    timestamp: datetime


class FollowTrackHop(BaseModel):
    """A single camera observation hop in an entity's journey."""
    hop_index: int
    camera_id: str
    local_track_id: str
    entered_at: datetime
    last_seen_at: datetime
    duration_seconds: float
    transition_confidence: float = 1.0
    from_camera: Optional[str] = None
    association_signals: Dict[str, Any] = Field(default_factory=dict)
    events_count: int = 0
    peak_threat: float = 0.0


class FollowTrackResponse(BaseModel):
    """Complete cross-camera journey for a global entity."""
    global_entity_id: str
    display_id: str
    entity_type: str
    status: str
    first_seen: datetime
    last_seen: datetime
    total_hops: int
    cameras_visited: List[str]
    hops: List[FollowTrackHop]


class PersonProfile(BaseModel):
    """Detailed profile for a global person entity."""
    global_entity_id: str
    display_id: str
    status: str
    current_camera_id: Optional[str] = None
    current_local_track_id: Optional[str] = None
    first_seen: datetime
    last_seen: datetime
    cameras_observed: List[str]
    local_tracks: Dict[str, List[str]]  # camera_id -> list of local track IDs
    transitions_count: int
    candidate_associations: List[CandidateAssociation] = Field(default_factory=list)
    face_observations: List[Dict[str, Any]] = Field(default_factory=list)
    incidents: List[Dict[str, Any]] = Field(default_factory=list)
    threat_level: str = "NORMAL"
    peak_threat: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VehicleProfile(BaseModel):
    """Detailed profile for a global vehicle entity."""
    global_entity_id: str
    display_id: str
    status: str
    current_camera_id: Optional[str] = None
    current_local_track_id: Optional[str] = None
    first_seen: datetime
    last_seen: datetime
    cameras_observed: List[str]
    local_tracks: Dict[str, List[str]]
    vehicle_type: str = "vehicle"
    plates_observed: List[Dict[str, Any]] = Field(default_factory=list)
    best_plate_text: Optional[str] = None
    best_plate_confidence: float = 0.0
    incidents: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GlobalEntitySummary(BaseModel):
    """Summary item for entity listings."""
    global_entity_id: str
    display_id: str
    entity_type: str
    status: str
    current_camera_id: Optional[str] = None
    current_local_track_id: Optional[str] = None
    first_seen: datetime
    last_seen: datetime
    cameras_count: int = 1
    has_candidates: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)
