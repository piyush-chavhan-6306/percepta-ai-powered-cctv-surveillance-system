"""
Border Intelligence Alerts REST API.
Provides endpoints to list security alerts, filter by camera/severity, and acknowledge alerts.
"""
import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status
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
    message: str = "Perimeter Security Alert"
    severity: str = "CRITICAL"
    is_acknowledged: bool = False


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
    parsed: List[AlertItem] = []

    for a in raw_alerts:
        msg = a.get("message")
        sev = a.get("severity")
        ack = a.get("is_acknowledged", False)

        if (not msg or not sev) and a.get("payload"):
            try:
                p = json.loads(a["payload"])
                if isinstance(p, dict):
                    msg = msg or p.get("message")
                    sev = sev or p.get("severity")
                    ack = ack or p.get("is_acknowledged", False)
            except Exception:
                pass

        parsed.append(
            AlertItem(
                seq_id=a["seq_id"],
                event_id=a["event_id"],
                timestamp=a["timestamp"],
                camera_id=a["camera_id"],
                track_id=str(a["track_id"]) if a.get("track_id") is not None else None,
                incident_id=a.get("incident_id"),
                confidence=a.get("confidence"),
                source=a["source"],
                payload=a["payload"],
                message=str(msg) if msg else "Security Perimeter Violation",
                severity=str(sev).upper() if sev else "CRITICAL",
                is_acknowledged=bool(ack),
            )
        )

    return AlertListResponse(count=len(parsed), alerts=parsed)


@router.post("/{event_id}/acknowledge")
async def acknowledge_alert(event_id: str) -> Dict[str, Any]:
    """Acknowledge a specific security alert event."""
    store = get_event_store()
    success = await store.acknowledge_alert(event_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert event '{event_id}' not found",
        )
    return {"event_id": event_id, "status": "acknowledged"}
