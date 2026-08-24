"""
Border Intelligence Alerts REST API.
Provides endpoints to list security alerts, filter by camera/severity, and acknowledge alerts.
"""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel

from backend.events.store import EventStore, get_event_store

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])


class AlertItem(BaseModel):
    seq_id: int
    event_id: str
    timestamp: str
    camera_id: str
    track_id: Optional[str] = None
    incident_id: Optional[str] = None
    confidence: Optional[float] = None
    source: str
    payload: str


class AlertListResponse(BaseModel):
    count: int
    alerts: List[AlertItem]


@router.get("", response_model=AlertListResponse)
async def list_alerts(
    camera_id: Optional[str] = Query(None, description="Filter alerts by camera ID"),
    severity: Optional[str] = Query(None, description="Filter alerts by severity level"),
    limit: int = Query(50, ge=1, le=500, description="Max alerts to return"),
) -> AlertListResponse:
    """Retrieve security alert events from durable SQLite WAL persistence."""
    store = get_event_store()
    raw_alerts = await store.get_alerts(camera_id=camera_id, severity=severity, limit=limit)
    return AlertListResponse(count=len(raw_alerts), alerts=raw_alerts)


@router.post("/{event_id}/acknowledge")
async def acknowledge_alert(event_id: str) -> Dict[str, Any]:
    """Acknowledge a specific security alert event."""
    from fastapi import HTTPException, status
    store = get_event_store()
    success = await store.acknowledge_alert(event_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert event '{event_id}' not found",
        )
    return {"event_id": event_id, "status": "acknowledged"}
