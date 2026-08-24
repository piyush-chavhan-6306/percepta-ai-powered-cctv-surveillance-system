"""
Border Intelligence Forensic Evidence REST API.
Provides endpoints for cryptographic verification of surveillance records and chain-of-custody audits.
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status

from backend.events.forensics import (
    EventVerificationResult,
    IntegrityAuditReport,
    get_forensics_engine,
)

router = APIRouter(prefix="/api/evidence", tags=["Forensic Evidence"])


@router.get("/verify/{event_id}", response_model=EventVerificationResult)
async def verify_event_authenticity(event_id: str) -> EventVerificationResult:
    """Cryptographically verify the authenticity and SHA-256 signature of a recorded surveillance event."""
    engine = get_forensics_engine()
    result = await engine.verify_event(event_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event record '{event_id}' not found in SQLite store",
        )
    return result


@router.get("/audit-integrity", response_model=IntegrityAuditReport)
async def audit_database_integrity(
    limit: int = Query(200, ge=10, le=1000, description="Number of recent records to audit"),
) -> IntegrityAuditReport:
    """
    Perform a complete cryptographic chain-of-custody audit on persisted surveillance event logs.
    Returns proof of non-tampering and root chain hash.
    """
    engine = get_forensics_engine()
    return await engine.audit_database_integrity(limit=limit)


@router.get("/snapshots/{incident_id}")
async def get_incident_snapshots(incident_id: str):
    """Retrieve list of visual JPEG evidence snapshots captured for an incident."""
    from backend.events.snapshots import get_snapshot_manager
    manager = get_snapshot_manager()
    snaps = manager.list_snapshots(incident_id)
    return {"incident_id": incident_id, "count": len(snaps), "snapshots": snaps}


@router.get("/snapshots/file/{filename}")
async def get_snapshot_image_file(filename: str):
    """Serve visual JPEG snapshot image file."""
    import os
    from fastapi.responses import FileResponse
    from backend.events.snapshots import get_snapshot_manager
    manager = get_snapshot_manager()
    file_path = manager.snapshot_dir / filename
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot file '{filename}' not found",
        )
    return FileResponse(str(file_path), media_type="image/jpeg")
