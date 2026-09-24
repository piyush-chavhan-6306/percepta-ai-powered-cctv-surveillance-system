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
    threat_score: Optional[float] = None
    threat_level: Optional[str] = None
    threat_reasons: Optional[List[str]] = None
    causal_chain: Optional[List[str]] = None
    evidence_snapshot_uri: Optional[str] = None
    face_snapshot_uri: Optional[str] = None
    anpr_snapshot_uri: Optional[str] = None
    best_frame_number: Optional[int] = None
    modality: str = "STANDARD"
    timeline_offset_sec: Optional[float] = None
    heading: Optional[str] = None
    speed_description: Optional[str] = None
    target_bbox: Optional[List[float]] = None
    plate_number: Optional[str] = None
    plate_confidence: Optional[float] = None
    plate_uncertain: bool = False
    face_confidence: Optional[float] = None


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
        t_score = None
        t_level = None
        t_reasons = None
        c_chain = None
        ev_snap = None
        face_snap = None
        anpr_snap = None
        best_frame = None
        modality = "STANDARD"
        t_offset = None
        heading = None
        speed_desc = None

        if a.get("payload"):
            try:
                p = json.loads(a["payload"])
                if isinstance(p, dict):
                    msg = msg or p.get("message")
                    sev = sev or p.get("severity")
                    ack = ack or p.get("is_acknowledged", False)
                    t_score = p.get("threat_score")
                    t_level = p.get("threat_level")
                    t_reasons = p.get("threat_reasons")
                    c_chain = p.get("causal_chain")
                    ev_snap = p.get("evidence_snapshot_uri")
                    face_snap = p.get("face_snapshot_uri")
                    anpr_snap = p.get("anpr_snapshot_uri")
                    best_frame = p.get("best_frame_number")
                    modality = p.get("modality", "STANDARD")
                    t_offset = p.get("timeline_offset_sec")
                    heading = p.get("heading")
                    speed_desc = p.get("speed_description")
                    target_bbox = p.get("target_bbox")
                    plate_num = p.get("plate_number")
                    plate_conf = p.get("plate_confidence")
                    plate_unc = p.get("plate_uncertain", False)
                    face_conf = p.get("face_confidence")
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
                threat_score=t_score,
                threat_level=t_level,
                threat_reasons=t_reasons,
                causal_chain=c_chain,
                evidence_snapshot_uri=ev_snap,
                face_snapshot_uri=face_snap,
                anpr_snapshot_uri=anpr_snap,
                best_frame_number=best_frame,
                modality=modality,
                timeline_offset_sec=t_offset,
                heading=heading,
                speed_description=speed_desc,
                target_bbox=target_bbox,
                plate_number=plate_num,
                plate_confidence=plate_conf,
                plate_uncertain=bool(plate_unc),
                face_confidence=face_conf,
            )
        )

    return AlertListResponse(count=len(parsed), alerts=parsed)


@router.post("/clear")
@router.delete("")
async def clear_alerts() -> Dict[str, Any]:
    """Clear all past security alert events from storage and reset in-memory detection states."""
    from backend.database import get_session_factory
    from sqlalchemy import text
    from backend.zones.security_zone import get_zone_monitor
    from backend.tracking.live_worker import get_worker_registry

    session_factory = get_session_factory()
    async with session_factory() as session:
        await session.execute(text("DELETE FROM events WHERE UPPER(event_type) IN ('ALERT', 'ZONE')"))
        await session.commit()

    # Reset in-memory detection states so subsequent intrusions alert immediately
    try:
        get_zone_monitor().reset()
        get_worker_registry().reset_all_zone_states()
    except Exception as reset_err:
        logger.warning(f"Error resetting zone monitor states on clear: {reset_err}")

    return {"status": "cleared", "message": "All past alerts cleared successfully"}


@router.post("/{event_id}/acknowledge")
@router.post("/{event_id}/ack")
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
