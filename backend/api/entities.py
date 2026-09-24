"""
PERCEPTA Defense — Global Entity REST API.

Provides endpoints for global entities, Follow-Track multi-camera hops,
Person and Vehicle Profiles, and candidate associations.
"""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from backend.entities.service import get_entity_manager
from backend.entities.models import (
    FollowTrackResponse,
    GlobalEntitySummary,
    PersonProfile,
    VehicleProfile,
)

router = APIRouter(prefix="/api/entities", tags=["Global Entities"])


@router.get("", response_model=List[GlobalEntitySummary])
async def list_global_entities(
    entity_type: Optional[str] = Query(None, description="Filter by person, vehicle, or unknown"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by active, lost, terminated"),
    camera_id: Optional[str] = Query(None, description="Filter by current camera ID"),
    limit: int = Query(100, ge=1, le=500),
) -> List[GlobalEntitySummary]:
    """List persistent global entities with filtering."""
    mgr = get_entity_manager()
    return await mgr.list_entities(
        entity_type=entity_type,
        status=status_filter,
        camera_id=camera_id,
        limit=limit,
    )


@router.get("/{entity_key}/follow", response_model=FollowTrackResponse)
@router.get("/{entity_key}/follow-track", response_model=FollowTrackResponse)
async def get_entity_follow_track(entity_key: str) -> FollowTrackResponse:
    """
    Follow Track — Returns ordered camera-hop trajectory for a global entity.
    Answers: CAM-01 (LOCAL-P17) -> CAM-02 (LOCAL-P04) -> CAM-03 (LOCAL-P12).
    """
    mgr = get_entity_manager()
    follow = await mgr.get_follow_track(entity_key)
    if not follow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Global entity '{entity_key}' not found",
        )
    return follow


@router.get("/{entity_key}/profile")
async def get_entity_profile(entity_key: str) -> Dict[str, Any]:
    """Retrieve full Person or Vehicle profile for a global entity."""
    mgr = get_entity_manager()
    entity = await mgr.get_entity_by_id_or_display(entity_key)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Global entity '{entity_key}' not found",
        )

    if entity.entity_type == "vehicle":
        prof = await mgr.get_vehicle_profile(entity_key)
        return prof.model_dump() if prof else {}
    else:
        prof = await mgr.get_person_profile(entity_key)
        return prof.model_dump() if prof else {}


@router.get("/{entity_key}")
async def get_global_entity(entity_key: str) -> Dict[str, Any]:
    """Get single global entity core attributes."""
    mgr = get_entity_manager()
    entity = await mgr.get_entity_by_id_or_display(entity_key)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Global entity '{entity_key}' not found",
        )
    return {
        "global_entity_id": entity.global_entity_id,
        "display_id": entity.display_id,
        "entity_type": entity.entity_type,
        "status": entity.status,
        "current_camera_id": entity.current_camera_id,
        "current_local_track_id": entity.current_local_track_id,
        "first_seen": entity.first_seen.isoformat(),
        "last_seen": entity.last_seen.isoformat(),
        "metadata": entity.meta or {},
    }
