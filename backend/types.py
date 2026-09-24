"""
PERCEPTA Defense — Canonical ID Types.

All IDs in the system use string UUIDs wrapped in typed aliases.
This prevents accidental cross-type ID comparisons and makes the
data flow explicit: CameraID ≠ SessionID ≠ TrackID ≠ EntityID.
"""
from typing import NewType

# Camera-level identifiers
CameraID = NewType("CameraID", str)
SessionID = NewType("SessionID", str)

# Tracking identifiers
LocalTrackID = NewType("LocalTrackID", str)
GlobalEntityID = NewType("GlobalEntityID", str)

# Event/incident identifiers
EventID = NewType("EventID", str)
IncidentID = NewType("IncidentID", str)
AlertID = NewType("AlertID", str)
EvidenceID = NewType("EvidenceID", str)

# Observation identifiers
FaceObservationID = NewType("FaceObservationID", str)
PlateObservationID = NewType("PlateObservationID", str)
WeaponObservationID = NewType("WeaponObservationID", str)

# Zone identifiers
ZoneID = NewType("ZoneID", str)
TransitionID = NewType("TransitionID", str)

# Assessment identifiers
AssessmentID = NewType("AssessmentID", str)
QueryID = NewType("QueryID", str)
