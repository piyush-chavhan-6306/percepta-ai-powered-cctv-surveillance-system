"""
Border Intelligence Security Zones & Virtual Boundaries REST API.
Provides endpoints for creating, listing, and managing spatial security zones and virtual tripwires.
"""
from typing import Any, Dict, List, Optional, Tuple
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.zones.security_zone import (
    SecurityZone,
    VirtualBoundary,
    ZoneSeverity,
    get_zone_monitor,
)

router = APIRouter(prefix="/api/zones", tags=["Security Zones"])


class CreateZoneRequest(BaseModel):
    zone_id: str
    name: str
    polygon: List[Tuple[float, float]] = Field(..., min_length=3, description="List of (x, y) coordinates")
    severity: str = "restricted"  # "info", "warning", "restricted", "critical"
    loitering_threshold_seconds: Optional[float] = 2.0
    loitering_debounce_seconds: float = 30.0


class CreateBoundaryRequest(BaseModel):
    boundary_id: str
    name: str
    pt1: Tuple[float, float]
    pt2: Tuple[float, float]
    severity: str = "critical"


class ZoneResponse(BaseModel):
    zone_id: str
    name: str
    polygon: List[Tuple[float, float]]
    severity: str
    is_active: bool
    loitering_threshold_seconds: Optional[float] = None


class BoundaryResponse(BaseModel):
    boundary_id: str
    name: str
    pt1: Tuple[float, float]
    pt2: Tuple[float, float]
    severity: str
    is_active: bool


class ZoneListResponse(BaseModel):
    zones: List[ZoneResponse]
    boundaries: List[BoundaryResponse]


@router.get("", response_model=ZoneListResponse)
async def list_zones_and_boundaries() -> ZoneListResponse:
    """List all active security zones and virtual tripwire boundaries."""
    monitor = get_zone_monitor()
    zones_list = [
        ZoneResponse(
            zone_id=z.zone_id,
            name=z.name,
            polygon=z.polygon,
            severity=z.severity.value,
            is_active=z.is_active,
            loitering_threshold_seconds=z.loitering_threshold_seconds,
        )
        for z in monitor.zones.values()
    ]
    boundaries_list = [
        BoundaryResponse(
            boundary_id=b.boundary_id,
            name=b.name,
            pt1=b.pt1,
            pt2=b.pt2,
            severity=b.severity.value,
            is_active=b.is_active,
        )
        for b in monitor.boundaries.values()
    ]
    return ZoneListResponse(zones=zones_list, boundaries=boundaries_list)


@router.post("", response_model=ZoneResponse)
async def create_security_zone(request: CreateZoneRequest) -> ZoneResponse:
    """Create a new polygon security zone."""
    monitor = get_zone_monitor()
    try:
        sev = ZoneSeverity(request.severity.lower())
    except ValueError:
        sev = ZoneSeverity.RESTRICTED

    zone = SecurityZone(
        zone_id=request.zone_id,
        name=request.name,
        polygon=request.polygon,
        severity=sev,
        loitering_threshold_seconds=request.loitering_threshold_seconds,
        loitering_debounce_seconds=request.loitering_debounce_seconds,
    )
    monitor.add_zone(zone)
    return ZoneResponse(
        zone_id=zone.zone_id,
        name=zone.name,
        polygon=zone.polygon,
        severity=zone.severity.value,
        is_active=zone.is_active,
        loitering_threshold_seconds=zone.loitering_threshold_seconds,
    )


@router.post("/boundary", response_model=BoundaryResponse)
async def create_virtual_boundary(request: CreateBoundaryRequest) -> BoundaryResponse:
    """Create a new virtual tripwire boundary line."""
    monitor = get_zone_monitor()
    try:
        sev = ZoneSeverity(request.severity.lower())
    except ValueError:
        sev = ZoneSeverity.CRITICAL

    boundary = VirtualBoundary(
        boundary_id=request.boundary_id,
        name=request.name,
        pt1=request.pt1,
        pt2=request.pt2,
        severity=sev,
    )
    monitor.add_boundary(boundary)
    return BoundaryResponse(
        boundary_id=boundary.boundary_id,
        name=boundary.name,
        pt1=boundary.pt1,
        pt2=boundary.pt2,
        severity=boundary.severity.value,
        is_active=boundary.is_active,
    )


@router.delete("/{zone_id}")
async def delete_zone_or_boundary(zone_id: str) -> Dict[str, Any]:
    """Delete a security zone or virtual boundary."""
    monitor = get_zone_monitor()
    if zone_id in monitor.zones:
        del monitor.zones[zone_id]
        return {"zone_id": zone_id, "status": "deleted", "type": "zone"}
    if zone_id in monitor.boundaries:
        del monitor.boundaries[zone_id]
        return {"zone_id": zone_id, "status": "deleted", "type": "boundary"}

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Zone or boundary '{zone_id}' not found",
    )


@router.get("/templates")
async def get_zone_templates():
    """Retrieve standard tactical security zone and virtual tripwire templates."""
    from backend.zones.templates import list_tactical_templates
    return {"templates": list_tactical_templates()}


@router.post("/apply-template")
async def apply_zone_template(request: dict):
    """Instantiate a tactical template into the active surveillance zone monitor."""
    from backend.zones.templates import apply_tactical_template
    tmpl_id = request.get("template_id")
    suffix = request.get("zone_id_suffix", "01")
    custom_name = request.get("custom_name")

    if not tmpl_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Field 'template_id' is required",
        )
    try:
        res = apply_tactical_template(template_id=tmpl_id, custom_name=custom_name, zone_id_suffix=suffix)
        return res
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))
