"""
Border Intelligence Incidents REST API.
Provides endpoints for incident timelines and aggregated incident management.
"""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from backend.events.store import get_event_store

router = APIRouter(prefix="/api/incidents", tags=["Incidents"])


class IncidentItem(BaseModel):
    incident_id: str
    camera_id: str
    total_events: int
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    status: str = "opened"


class IncidentListResponse(BaseModel):
    count: int
    incidents: List[IncidentItem]


class IncidentTimelineResponse(BaseModel):
    incident_id: str
    count: int
    timeline: List[Dict[str, Any]]


@router.get("", response_model=IncidentListResponse)
async def list_incidents(
    camera_id: Optional[str] = None,
    limit: int = 50,
) -> IncidentListResponse:
    """Retrieve aggregated surveillance incidents list."""
    store = get_event_store()
    incidents = await store.get_incidents(camera_id=camera_id, limit=limit)
    return IncidentListResponse(count=len(incidents), incidents=incidents)


@router.get("/{incident_id}", response_model=IncidentTimelineResponse)
async def get_incident_timeline(incident_id: str) -> IncidentTimelineResponse:
    """Retrieve full chronological timeline of all events linked to an incident."""
    store = get_event_store()
    timeline = await store.get_incident_timeline(incident_id)
    if not timeline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found",
        )
    return IncidentTimelineResponse(
        incident_id=incident_id,
        count=len(timeline),
        timeline=timeline,
    )


@router.get("/{incident_id}/dossier")
async def get_incident_dossier(incident_id: str):
    """
    Generate a complete, tamper-verified Tactical Incident Dossier and Situation Report (SitRep).
    Aggregates motion vectors, zone infractions, duration, and cryptographic SHA-256 tokens.
    """
    from backend.incidents.dossier import get_dossier_generator
    generator = get_dossier_generator()
    dossier = await generator.generate_dossier(incident_id)
    if not dossier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found",
        )
    return dossier


@router.post("/{incident_id}/notes")
async def add_incident_note(incident_id: str, request: dict):
    """Append a timestamped human operator annotation or tactical action note to an incident."""
    from backend.incidents.annotations import get_annotation_manager
    manager = get_annotation_manager()
    callsign = request.get("operator_callsign", "Duty Officer")
    note = request.get("note", "").strip()
    disposition = request.get("disposition", "INVESTIGATING")

    if not note:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Note content cannot be empty",
        )

    ann = await manager.add_annotation(
        incident_id=incident_id,
        operator_callsign=callsign,
        note=note,
        disposition=disposition,
    )
    return ann


@router.get("/{incident_id}/notes")
async def list_incident_notes(incident_id: str):
    """Retrieve chronological audit trail of all operator notes linked to an incident."""
    from backend.incidents.annotations import get_annotation_manager
    manager = get_annotation_manager()
    notes = await manager.get_annotations(incident_id)
    return {"incident_id": incident_id, "count": len(notes), "annotations": notes}


@router.post("/{incident_id}/acknowledge")
async def acknowledge_incident(incident_id: str, request: Optional[dict] = None) -> Dict[str, Any]:
    """Acknowledge an incident and its associated operator alert."""
    from backend.incidents.service import get_incident_manager
    mgr = get_incident_manager()
    caller = (request or {}).get("operator", "Operator")
    inc = await mgr.acknowledge_incident(incident_id=incident_id, acknowledged_by=caller)
    if not inc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found",
        )
    return {"status": "success", "incident_id": incident_id, "incident_status": inc.status}


@router.post("/{incident_id}/resolve")
async def resolve_incident(incident_id: str, request: Optional[dict] = None) -> Dict[str, Any]:
    """Resolve an incident and clear active alert state."""
    from backend.incidents.service import get_incident_manager
    mgr = get_incident_manager()
    req = request or {}
    resolver = req.get("operator", "Operator")
    notes = req.get("notes", "Situation normalized")
    inc = await mgr.resolve_incident(incident_id=incident_id, resolved_by=resolver, resolution_notes=notes)
    if not inc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found",
        )
    return {"status": "success", "incident_id": incident_id, "incident_status": inc.status}


@router.get("/{incident_id}/comprehensive-timeline")
async def get_comprehensive_timeline(incident_id: str) -> Dict[str, Any]:
    """Phase 16: Complete timeline covering What, Who, Where, When, How Serious, Why, Evidence, Status, Where Now."""
    from backend.incidents.service import get_incident_manager
    mgr = get_incident_manager()
    timeline_data = await mgr.get_incident_timeline(incident_id)
    if not timeline_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found",
        )
    return timeline_data


@router.get("/metrics/deduplication")
async def get_deduplication_metrics() -> Dict[str, Any]:
    """Get telemetry metrics proving alert deduplication rate."""
    from backend.incidents.service import get_incident_manager
    mgr = get_incident_manager()
    return mgr.get_deduplication_metrics()

