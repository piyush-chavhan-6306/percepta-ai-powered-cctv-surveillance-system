"""
PERCEPTA Defense — Global Entity Management Service.

Maintains persistent global entities above camera-local tracks.
Manages cross-camera association lifecycle, candidate associations,
Follow-Track histories, and Person/Vehicle profiles.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import column, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_session_factory
from backend.database.schema import (
    Camera,
    CameraTransition,
    Event,
    FaceObservation,
    GlobalEntity,
    Incident,
    LocalTrack,
    PlateObservation,
)
from backend.entities.models import (
    CandidateAssociation,
    EntityStatus,
    EntityType,
    FollowTrackHop,
    FollowTrackResponse,
    GlobalEntitySummary,
    PersonProfile,
    VehicleProfile,
)

logger = logging.getLogger(__name__)


class GlobalEntityManager:
    """Service managing persistent global entities across cameras."""

    def __init__(self) -> None:
        self._next_person_num = 1
        self._next_vehicle_num = 1

    def _next_display_id(self, entity_type: str, session_max: Optional[int] = None) -> str:
        """Generate human-readable canonical display ID."""
        clean_type = entity_type.lower()
        if "person" in clean_type:
            num = session_max if session_max else self._next_person_num
            self._next_person_num = num + 1
            return f"GLOBAL-PERSON-{num:03d}"
        elif "vehicle" in clean_type or "car" in clean_type or "truck" in clean_type:
            num = session_max if session_max else self._next_vehicle_num
            self._next_vehicle_num = num + 1
            return f"GLOBAL-VEHICLE-{num:03d}"
        else:
            num = session_max if session_max else self._next_person_num
            self._next_person_num = num + 1
            return f"GLOBAL-ENTITY-{num:03d}"

    async def create_entity(
        self,
        entity_type: str = "person",
        camera_id: Optional[str] = None,
        local_track_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        meta: Optional[Dict[str, Any]] = None,
        display_id_override: Optional[str] = None,
    ) -> GlobalEntity:
        """Create a new global entity in DB."""
        now = timestamp or datetime.now(timezone.utc)
        factory = get_session_factory()
        async with factory() as session:
            # Determine display ID
            if display_id_override:
                exist_stmt = select(GlobalEntity).where(GlobalEntity.display_id == display_id_override)
                existing = (await session.execute(exist_stmt)).scalar_one_or_none()
                if existing:
                    existing.last_seen = now
                    if camera_id:
                        existing.current_camera_id = camera_id
                    if local_track_id:
                        existing.current_local_track_id = str(local_track_id)
                    await session.commit()
                    return existing
                display_id = display_id_override
            else:
                # Find current count and ensure unique candidate
                count_stmt = select(func.count(GlobalEntity.global_entity_id)).where(
                    GlobalEntity.entity_type == entity_type
                )
                curr_count = (await session.execute(count_stmt)).scalar() or 0
                candidate_idx = curr_count + 1
                while True:
                    candidate_id = self._next_display_id(entity_type, candidate_idx)
                    chk_stmt = select(GlobalEntity.global_entity_id).where(GlobalEntity.display_id == candidate_id)
                    if not (await session.execute(chk_stmt)).scalar_one_or_none():
                        display_id = candidate_id
                        break
                    candidate_idx += 1

            entity = GlobalEntity(
                global_entity_id=str(uuid.uuid4()),
                display_id=display_id,
                entity_type=entity_type,
                first_seen=now,
                last_seen=now,
                current_camera_id=camera_id,
                current_local_track_id=local_track_id,
                status=EntityStatus.ACTIVE.value,
                meta=meta or {},
            )
            session.add(entity)

            # Link local track if provided
            if local_track_id and camera_id:
                track_stmt = select(LocalTrack).where(
                    LocalTrack.local_track_id == str(local_track_id),
                    LocalTrack.camera_id == camera_id,
                )
                res = await session.execute(track_stmt)
                lt = res.scalar_one_or_none()
                if lt:
                    lt.global_entity_id = entity.global_entity_id

            await session.commit()
            logger.info(f"GlobalEntityManager: created {display_id} ({entity_type}) on {camera_id}")
            return entity

    async def get_entity_by_id_or_display(self, entity_key: str) -> Optional[GlobalEntity]:
        """Fetch GlobalEntity by UUID or display_id (e.g. GLOBAL-PERSON-042)."""
        clean_key = entity_key.strip()
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(GlobalEntity).where(
                (GlobalEntity.global_entity_id == clean_key) |
                (GlobalEntity.display_id == clean_key) |
                (GlobalEntity.display_id == clean_key.upper())
            )
            res = await session.execute(stmt)
            return res.scalar_one_or_none()

    async def list_entities(
        self,
        entity_type: Optional[str] = None,
        status: Optional[str] = None,
        camera_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[GlobalEntitySummary]:
        """List global entities with filtering."""
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(GlobalEntity)
            if entity_type:
                stmt = stmt.where(GlobalEntity.entity_type == entity_type)
            if status:
                stmt = stmt.where(GlobalEntity.status == status)
            if camera_id:
                stmt = stmt.where(GlobalEntity.current_camera_id == camera_id)

            stmt = stmt.order_by(GlobalEntity.last_seen.desc()).limit(limit)
            res = await session.execute(stmt)
            entities = res.scalars().all()

            summaries = []
            for ent in entities:
                meta = ent.meta or {}
                candidates = meta.get("candidate_associations", [])
                visited_cams = meta.get("cameras_visited", [ent.current_camera_id] if ent.current_camera_id else [])
                summaries.append(GlobalEntitySummary(
                    global_entity_id=ent.global_entity_id,
                    display_id=ent.display_id,
                    entity_type=ent.entity_type,
                    status=ent.status,
                    current_camera_id=ent.current_camera_id,
                    current_local_track_id=ent.current_local_track_id,
                    first_seen=ent.first_seen,
                    last_seen=ent.last_seen,
                    cameras_count=len(set(c for c in visited_cams if c)),
                    has_candidates=bool(candidates),
                    metadata=meta,
                ))
            return summaries

    async def associate_local_track(
        self,
        global_entity_id: str,
        camera_id: str,
        local_track_id: str,
        confidence: float,
        signals: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
    ) -> Optional[CameraTransition]:
        """
        Associate a camera-local track to an existing global entity.
        If camera_id differs from current camera, records a CameraTransition.
        """
        now = timestamp or datetime.now(timezone.utc)
        factory = get_session_factory()
        async with factory() as session:
            ent = await session.get(GlobalEntity, global_entity_id)
            if not ent:
                return None

            transition_record = None
            old_cam = ent.current_camera_id
            old_track = ent.current_local_track_id

            # If switching camera or confirmed transition
            if old_cam and old_cam != camera_id and old_track:
                transition_record = CameraTransition(
                    transition_id=str(uuid.uuid4()),
                    global_entity_id=global_entity_id,
                    from_camera_id=old_cam,
                    from_local_track_id=old_track,
                    to_camera_id=camera_id,
                    to_local_track_id=str(local_track_id),
                    association_confidence=confidence,
                    transition_time=now,
                    association_signals=signals or {},
                )
                session.add(transition_record)

            # Update entity state
            ent.current_camera_id = camera_id
            ent.current_local_track_id = str(local_track_id)
            ent.last_seen = now
            ent.status = EntityStatus.ACTIVE.value

            meta = dict(ent.meta or {})
            visited = set(meta.get("cameras_visited", []))
            visited.add(camera_id)
            meta["cameras_visited"] = list(visited)
            meta["last_association_confidence"] = confidence
            meta["last_association_signals"] = signals or {}
            ent.meta = meta

            # Link local track row in DB
            track_stmt = select(LocalTrack).where(
                LocalTrack.local_track_id == str(local_track_id),
                LocalTrack.camera_id == camera_id,
            )
            res = await session.execute(track_stmt)
            lt = res.scalar_one_or_none()
            if lt:
                lt.global_entity_id = global_entity_id

            await session.commit()
            return transition_record

    async def update_entity_location(
        self,
        entity_key: str,
        camera_id: str,
        local_track_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> Optional[GlobalEntity]:
        """Update an entity's current camera and local track."""
        now = timestamp or datetime.now(timezone.utc)
        factory = get_session_factory()
        async with factory() as session:
            ent = await self.get_entity_by_id_or_display(entity_key)
            if not ent:
                return None
            ent_in_sess = await session.get(GlobalEntity, ent.global_entity_id)
            if not ent_in_sess:
                return None
            ent_in_sess.current_camera_id = camera_id
            if local_track_id:
                ent_in_sess.current_local_track_id = str(local_track_id)
            ent_in_sess.last_seen = now
            ent_in_sess.status = EntityStatus.ACTIVE.value
            await session.commit()
            return ent_in_sess

    async def record_candidate_association(
        self,
        source_entity_id: str,
        candidate_entity_id: str,
        confidence: float,
        signals: Optional[Dict[str, Any]] = None,
        status: str = "candidate",
    ) -> CandidateAssociation:
        """Record and return candidate association model."""
        now = datetime.now(timezone.utc)
        sig = signals or {}
        cand = CandidateAssociation(
            candidate_entity_id=candidate_entity_id,
            candidate_display_id=candidate_entity_id,
            similarity_score=confidence,
            margin=sig.get("margin", 0.0),
            reason=sig.get("reason", "Candidate similarity evaluated"),
            status=status,
            confidence=confidence,
            timestamp=now,
        )
        return cand

    async def add_candidate_association(
        self,
        primary_entity_id: str,
        candidate_entity_id: str,
        similarity_score: float,
        margin: float,
        reason: str,
        camera_id: str,
        local_track_id: str,
    ) -> None:
        """
        Record candidate association without merging when confidence is ambiguous.
        Prevents false merges while preserving Re-ID intelligence for the operator.
        """
        now = datetime.now(timezone.utc)
        factory = get_session_factory()
        async with factory() as session:
            ent = await session.get(GlobalEntity, primary_entity_id)
            cand = await session.get(GlobalEntity, candidate_entity_id)
            if not ent or not cand:
                return

            meta = dict(ent.meta or {})
            candidates = meta.get("candidate_associations", [])
            candidate_item = {
                "candidate_entity_id": cand.global_entity_id,
                "candidate_display_id": cand.display_id,
                "similarity_score": round(similarity_score, 3),
                "margin": round(margin, 3),
                "reason": reason,
                "camera_id": camera_id,
                "local_track_id": str(local_track_id),
                "timestamp": now.isoformat(),
            }
            # Append if not already recorded recently
            candidates.append(candidate_item)
            meta["candidate_associations"] = candidates[-10:]  # keep last 10
            ent.meta = meta
            await session.commit()
            logger.info(
                f"GlobalEntityManager: Candidate association {ent.display_id} <-> {cand.display_id} "
                f"(score={similarity_score:.2f}, margin={margin:.2f}) [NOT MERGED]"
            )

    async def get_follow_track(self, entity_key: str) -> Optional[FollowTrackResponse]:
        """
        Compute ordered camera-hop trajectory for a global entity.
        Returns: CAM-01 (LOCAL-P17) -> CAM-02 (LOCAL-P04) -> CAM-03 (LOCAL-P12)
        with timestamps, dwell times, and transitions.
        """
        entity = await self.get_entity_by_id_or_display(entity_key)
        if not entity:
            return None

        eid = entity.global_entity_id
        factory = get_session_factory()
        async with factory() as session:
            # 1. Fetch transitions in chronological order
            trans_stmt = select(CameraTransition).where(
                CameraTransition.global_entity_id == eid
            ).order_by(CameraTransition.transition_time.asc())
            trans_res = await session.execute(trans_stmt)
            transitions = trans_res.scalars().all()

            # 2. Fetch all local tracks linked to this entity
            tracks_stmt = select(LocalTrack).where(
                LocalTrack.global_entity_id == eid
            ).order_by(LocalTrack.first_seen.asc())
            tracks_res = await session.execute(tracks_stmt)
            local_tracks = tracks_res.scalars().all()

            # Build hops
            hops: List[FollowTrackHop] = []
            visited_cams: List[str] = []

            if transitions and len(local_tracks) <= 1:
                # Reconstruct hops from transition chain
                first_t = transitions[0]
                t0 = first_t.transition_time.replace(tzinfo=timezone.utc) if first_t.transition_time.tzinfo is None else first_t.transition_time
                e0 = entity.first_seen.replace(tzinfo=timezone.utc) if entity.first_seen.tzinfo is None else entity.first_seen
                hops.append(FollowTrackHop(
                    hop_index=1,
                    camera_id=first_t.from_camera_id,
                    local_track_id=first_t.from_local_track_id,
                    entered_at=e0,
                    last_seen_at=t0,
                    duration_seconds=max(0.0, (t0 - e0).total_seconds()),
                    transition_confidence=1.0,
                    from_camera=None,
                ))
                visited_cams.append(first_t.from_camera_id)

                for idx, t in enumerate(transitions):
                    next_time = transitions[idx+1].transition_time if idx + 1 < len(transitions) else entity.last_seen
                    t_in = t.transition_time.replace(tzinfo=timezone.utc) if t.transition_time.tzinfo is None else t.transition_time
                    t_out = next_time.replace(tzinfo=timezone.utc) if next_time.tzinfo is None else next_time
                    hops.append(FollowTrackHop(
                        hop_index=idx + 2,
                        camera_id=t.to_camera_id,
                        local_track_id=t.to_local_track_id,
                        entered_at=t_in,
                        last_seen_at=t_out,
                        duration_seconds=max(0.0, (t_out - t_in).total_seconds()),
                        transition_confidence=t.association_confidence,
                        from_camera=t.from_camera_id,
                        association_signals=t.association_signals or {},
                    ))
                    if t.to_camera_id not in visited_cams:
                        visited_cams.append(t.to_camera_id)
            elif not local_tracks and entity.current_camera_id:
                # Single initial hop from entity fields
                first_seen = entity.first_seen
                last_seen = entity.last_seen
                dur = max(0.0, (last_seen - first_seen).total_seconds())
                hops.append(FollowTrackHop(
                    hop_index=1,
                    camera_id=entity.current_camera_id,
                    local_track_id=entity.current_local_track_id or "LOCAL-1",
                    entered_at=first_seen,
                    last_seen_at=last_seen,
                    duration_seconds=dur,
                    transition_confidence=1.0,
                    from_camera=None,
                ))
                visited_cams.append(entity.current_camera_id)
            else:
                for idx, lt in enumerate(local_tracks):
                    dur = max(0.0, (lt.last_seen - lt.first_seen).total_seconds())
                    from_cam = None
                    conf = 1.0
                    signals = {}
                    if idx > 0 and transitions:
                        # match corresponding transition
                        for t in transitions:
                            if t.to_camera_id == lt.camera_id and t.to_local_track_id == lt.local_track_id:
                                from_cam = t.from_camera_id
                                conf = t.association_confidence
                                signals = t.association_signals or {}
                                break

                    hops.append(FollowTrackHop(
                        hop_index=idx + 1,
                        camera_id=lt.camera_id,
                        local_track_id=lt.local_track_id,
                        entered_at=lt.first_seen,
                        last_seen_at=lt.last_seen,
                        duration_seconds=dur,
                        transition_confidence=conf,
                        from_camera=from_cam,
                        association_signals=signals,
                    ))
                    if lt.camera_id not in visited_cams:
                        visited_cams.append(lt.camera_id)

            return FollowTrackResponse(
                global_entity_id=entity.global_entity_id,
                display_id=entity.display_id,
                entity_type=entity.entity_type,
                status=entity.status,
                first_seen=entity.first_seen,
                last_seen=entity.last_seen,
                total_hops=len(hops),
                cameras_visited=visited_cams,
                hops=hops,
            )

    async def get_person_profile(self, entity_key: str) -> Optional[PersonProfile]:
        """Compile complete Person Profile without biometric identification."""
        entity = await self.get_entity_by_id_or_display(entity_key)
        if not entity:
            return None

        eid = entity.global_entity_id
        factory = get_session_factory()
        async with factory() as session:
            # 1. Fetch local tracks
            tracks_stmt = select(LocalTrack).where(LocalTrack.global_entity_id == eid)
            tracks_res = await session.execute(tracks_stmt)
            tracks = tracks_res.scalars().all()

            local_track_map: Dict[str, List[str]] = {}
            cameras_observed = set()
            for t in tracks:
                local_track_map.setdefault(t.camera_id, []).append(t.local_track_id)
                cameras_observed.add(t.camera_id)

            if entity.current_camera_id:
                cameras_observed.add(entity.current_camera_id)
                if entity.current_local_track_id:
                    local_track_map.setdefault(entity.current_camera_id, []).append(entity.current_local_track_id)

            # 2. Fetch face observations linked to this entity or its tracks
            face_stmt = select(FaceObservation).where(
                FaceObservation.global_entity_id == eid
            ).order_by(FaceObservation.timestamp.desc()).limit(10)
            face_res = await session.execute(face_stmt)
            faces = [
                {
                    "observation_id": f.observation_id,
                    "camera_id": f.camera_id,
                    "timestamp": f.timestamp.isoformat(),
                    "confidence": f.confidence,
                    "quality_score": f.quality_score,
                    "crop_path": f.face_crop_path,
                }
                for f in face_res.scalars().all()
            ]

            # 3. Fetch incidents where this entity is primary target
            inc_stmt = select(Incident).where(
                Incident.primary_entity_id == eid
            ).order_by(Incident.created_at.desc()).limit(10)
            inc_res = await session.execute(inc_stmt)
            incidents = [
                {
                    "incident_id": i.incident_id,
                    "incident_type": i.incident_type,
                    "status": i.status,
                    "severity": i.severity,
                    "created_at": i.created_at.isoformat(),
                    "peak_threat": i.peak_threat,
                }
                for i in inc_res.scalars().all()
            ]

            # Transitions count
            trans_count_stmt = select(func.count(CameraTransition.transition_id)).where(
                CameraTransition.global_entity_id == eid
            )
            trans_count = (await session.execute(trans_count_stmt)).scalar() or 0

            meta = entity.meta or {}
            raw_cands = meta.get("candidate_associations", [])
            candidate_objs = [
                CandidateAssociation(
                    candidate_entity_id=c["candidate_entity_id"],
                    candidate_display_id=c["candidate_display_id"],
                    similarity_score=c["similarity_score"],
                    margin=c.get("margin", 0.0),
                    reason=c.get("reason", ""),
                    camera_id=c.get("camera_id", ""),
                    local_track_id=c.get("local_track_id", ""),
                    timestamp=datetime.fromisoformat(c["timestamp"]) if "timestamp" in c else entity.last_seen,
                )
                for c in raw_cands if isinstance(c, dict)
            ]

            peak_threat = max([i["peak_threat"] for i in incidents] + [0.0])
            threat_level = "CRITICAL" if peak_threat >= 85 else ("HIGH" if peak_threat >= 70 else ("MEDIUM" if peak_threat >= 50 else ("LOW" if peak_threat >= 30 else "NORMAL")))

            return PersonProfile(
                global_entity_id=entity.global_entity_id,
                display_id=entity.display_id,
                status=entity.status,
                current_camera_id=entity.current_camera_id,
                current_local_track_id=entity.current_local_track_id,
                first_seen=entity.first_seen,
                last_seen=entity.last_seen,
                cameras_observed=list(cameras_observed),
                local_tracks=local_track_map,
                transitions_count=trans_count,
                candidate_associations=candidate_objs,
                face_observations=faces,
                incidents=incidents,
                threat_level=threat_level,
                peak_threat=peak_threat,
                metadata=meta,
            )

    async def get_vehicle_profile(self, entity_key: str) -> Optional[VehicleProfile]:
        """Compile complete Vehicle Profile."""
        entity = await self.get_entity_by_id_or_display(entity_key)
        if not entity:
            return None

        eid = entity.global_entity_id
        factory = get_session_factory()
        async with factory() as session:
            # Local tracks
            tracks_stmt = select(LocalTrack).where(LocalTrack.global_entity_id == eid)
            tracks_res = await session.execute(tracks_stmt)
            tracks = tracks_res.scalars().all()

            local_track_map: Dict[str, List[str]] = {}
            cameras_observed = set()
            for t in tracks:
                local_track_map.setdefault(t.camera_id, []).append(t.local_track_id)
                cameras_observed.add(t.camera_id)

            if entity.current_camera_id:
                cameras_observed.add(entity.current_camera_id)
                if entity.current_local_track_id:
                    local_track_map.setdefault(entity.current_camera_id, []).append(entity.current_local_track_id)

            # Plate observations
            plates_stmt = select(PlateObservation).where(
                PlateObservation.global_entity_id == eid
            ).order_by(PlateObservation.plate_confidence.desc())
            plates_res = await session.execute(plates_stmt)
            plates = plates_res.scalars().all()

            plates_data = [
                {
                    "observation_id": p.observation_id,
                    "plate_text": p.plate_text,
                    "confidence": p.plate_confidence or 0.0,
                    "camera_id": p.camera_id,
                    "timestamp": p.timestamp.isoformat(),
                    "crop_path": p.plate_crop_path,
                }
                for p in plates
            ]

            best_text = plates[0].plate_text if plates else None
            best_conf = plates[0].plate_confidence if plates and plates[0].plate_confidence is not None else 0.0

            # Incidents
            inc_stmt = select(Incident).where(
                Incident.primary_entity_id == eid
            ).order_by(Incident.created_at.desc())
            inc_res = await session.execute(inc_stmt)
            incidents = [
                {
                    "incident_id": i.incident_id,
                    "incident_type": i.incident_type,
                    "status": i.status,
                    "severity": i.severity,
                    "created_at": i.created_at.isoformat(),
                }
                for i in inc_res.scalars().all()
            ]

            return VehicleProfile(
                global_entity_id=entity.global_entity_id,
                display_id=entity.display_id,
                status=entity.status,
                current_camera_id=entity.current_camera_id,
                current_local_track_id=entity.current_local_track_id,
                first_seen=entity.first_seen,
                last_seen=entity.last_seen,
                cameras_observed=list(cameras_observed),
                local_tracks=local_track_map,
                vehicle_type=entity.entity_type,
                plates_observed=plates_data,
                best_plate_text=best_text,
                best_plate_confidence=best_conf,
                incidents=incidents,
                metadata=entity.meta or {},
            )


global_entity_manager = GlobalEntityManager()


def get_entity_manager() -> GlobalEntityManager:
    return global_entity_manager
