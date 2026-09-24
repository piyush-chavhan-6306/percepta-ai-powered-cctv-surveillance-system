"""
PERCEPTA Event Store — Normalized Persistence Layer.

Persists internal pipeline events into SQLite WAL table 'events'.
Enforces the Persist-Before-Publish contract: events are guaranteed to be
written and committed to the database before they are dispatched onto the EventBus.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import column, func, literal_column, select, text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.database import get_session_factory
from backend.database.schema import Event
from backend.events.bus import EventBus, get_event_bus
from backend.events.schema import BaseEvent

logger = logging.getLogger(__name__)


class EventSequenceId(int):
    """Integer sequence ID (compatible with int comparisons like > 0) that carries event_id string."""
    def __new__(cls, val: int, event_id: str = ""):
        obj = super().__new__(cls, int(val))
        obj.event_id = str(event_id)
        return obj


class EventStore:
    """
    Durable Event Store using the normalized 'events' table.
    Enforces atomic batch commits and the Persist-Before-Publish contract.
    """

    def __init__(
        self,
        bus: Optional[EventBus] = None,
        max_retries: int = 5,
    ) -> None:
        self.bus = bus or get_event_bus()
        self.max_retries = max_retries
        self._stats_cache = None
        self._stats_cache_ttl = 5.0

    async def record_events_batch(
        self,
        events: List[BaseEvent],
        session: Optional[AsyncSession] = None,
        publish: bool = True,
    ) -> List[EventSequenceId]:
        """
        Atomically persist a batch of events in a single SQLite WAL transaction.
        Enforces Persist-Before-Publish: publishes all events only after commit succeeds.
        Returns list of EventSequenceId (int sequence IDs with .event_id string attribute).
        """
        if not events:
            return []

        log_entries = []
        for ev in events:
            if hasattr(ev, "model_dump"):
                m = ev.model_dump(mode="json")
            elif hasattr(ev, "dict"):
                m = ev.dict()
            else:
                m = {}
            log_entries.append(
                Event(
                    event_id=str(ev.event_id),
                    event_type=ev.event_type.value if hasattr(ev.event_type, "value") else str(ev.event_type),
                    timestamp=ev.timestamp,
                    camera_id=ev.camera_id,
                    session_id=None,
                    local_track_id=getattr(ev, "track_id", None),
                    global_entity_id=getattr(ev, "global_person_id", None),
                    zone_id=getattr(ev, "zone_id", None),
                    incident_id=getattr(ev, "incident_id", None),
                    entity_type=getattr(ev, "object_class", None),
                    confidence=getattr(ev, "confidence", None),
                    source=ev.source.value if hasattr(ev.source, "value") else str(ev.source),
                    meta=m,
                )
            )

        if session is not None:
            session.add_all(log_entries)
            await session.flush()
            ev_ids = [entry.event_id for entry in log_entries]
            # Fetch rowids
            rowid_res = await session.execute(
                select(Event.event_id, column("rowid").label("seq_id")).where(Event.event_id.in_(ev_ids))
            )
            id_map = {r.event_id: r.seq_id for r in rowid_res}
            seq_results = [EventSequenceId(id_map.get(eid, 0), eid) for eid in ev_ids]
            if publish:
                for ev in events:
                    await self.bus.publish(ev)
            return seq_results

        factory = get_session_factory()
        last_error = None

        for attempt in range(self.max_retries):
            try:
                async with factory() as local_session:
                    local_session.add_all(log_entries)
                    await local_session.commit()
                    ev_ids = [entry.event_id for entry in log_entries]

                    rowid_res = await local_session.execute(
                        select(Event.event_id, column("rowid").label("seq_id")).where(Event.event_id.in_(ev_ids))
                    )
                    id_map = {r.event_id: r.seq_id for r in rowid_res}
                    seq_results = [EventSequenceId(id_map.get(eid, 0), eid) for eid in ev_ids]

                    if publish:
                        for ev in events:
                            await self.bus.publish(ev)
                    return seq_results
            except (OperationalError, DBAPIError) as err:
                last_error = err
                backoff_ms = (2 ** attempt) * 10 + (attempt * 5)
                await asyncio.sleep(backoff_ms / 1000.0)
            except Exception as err:
                raise err

        logger.error(f"EventStore failed to persist event batch after {self.max_retries} attempts: {last_error}")
        raise last_error or RuntimeError("Failed to persist event batch due to database write contention")

    async def record_event(
        self,
        event: BaseEvent,
        session: Optional[AsyncSession] = None,
        publish: bool = True,
    ) -> EventSequenceId:
        """Persist single event, return EventSequenceId (int subclass)."""
        res = await self.record_events_batch([event], session=session, publish=publish)
        return res[0] if res else EventSequenceId(0, "")

    async def get_events(
        self,
        since: Optional[datetime] = None,
        after_seq: Optional[int] = None,
        camera_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100,
        newest_first: bool = False,
        session: Optional[AsyncSession] = None,
    ) -> List[Dict[str, Any]]:
        """
        Durable Event Replay API with deterministic ordering:
        ORDER BY timestamp ASC, rowid ASC (or DESC if newest_first=True)
        """
        query = select(Event, column("rowid").label("seq_id"))

        if after_seq is not None:
            query = query.where(column("rowid") > after_seq)
        if since is not None:
            query = query.where(Event.timestamp >= since)
        if camera_id is not None:
            query = query.where(Event.camera_id == camera_id)
        if event_type is not None:
            query = query.where(Event.event_type == event_type)

        if newest_first:
            query = query.order_by(Event.timestamp.desc(), column("rowid").desc())
        else:
            query = query.order_by(Event.timestamp.asc(), column("rowid").asc())
        query = query.limit(limit)

        async def _exec(s: AsyncSession) -> List[Dict[str, Any]]:
            result = await s.execute(query)
            rows = result.all()
            output = []
            for r in rows:
                ev = r.Event
                meta_dict = ev.meta if isinstance(ev.meta, dict) else (
                    json.loads(ev.meta) if isinstance(ev.meta, str) and ev.meta else {}
                )
                output.append({
                    "seq_id": int(r.seq_id),
                    "event_id": ev.event_id,
                    "event_type": ev.event_type,
                    "timestamp": ev.timestamp.isoformat(),
                    "camera_id": ev.camera_id,
                    "session_id": ev.session_id,
                    "local_track_id": ev.local_track_id,
                    "track_id": ev.local_track_id,
                    "global_entity_id": ev.global_entity_id,
                    "global_person_id": ev.global_entity_id,
                    "zone_id": ev.zone_id,
                    "incident_id": ev.incident_id,
                    "entity_type": ev.entity_type,
                    "confidence": ev.confidence,
                    "source": ev.source,
                    "payload": json.dumps(meta_dict),
                    "parsed_payload": meta_dict,
                    "metadata": meta_dict,
                    "evidence_id": ev.evidence_id,
                })
            return output

        if session is not None:
            return await _exec(session)

        factory = get_session_factory()
        async with factory() as local_session:
            return await _exec(local_session)

    async def get_incident_timeline(
        self,
        incident_id: str,
        session: Optional[AsyncSession] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve all events related to an incident ordered deterministically."""
        query = (
            select(Event, column("rowid").label("seq_id"))
            .where(Event.incident_id == incident_id)
            .order_by(Event.timestamp.asc(), column("rowid").asc())
        )

        async def _exec(s: AsyncSession) -> List[Dict[str, Any]]:
            result = await s.execute(query)
            rows = result.all()
            output = []
            for r in rows:
                ev = r.Event
                meta_dict = ev.meta if isinstance(ev.meta, dict) else (
                    json.loads(ev.meta) if isinstance(ev.meta, str) and ev.meta else {}
                )
                output.append({
                    "seq_id": int(r.seq_id),
                    "event_id": ev.event_id,
                    "event_type": ev.event_type,
                    "timestamp": ev.timestamp.isoformat(),
                    "camera_id": ev.camera_id,
                    "session_id": ev.session_id,
                    "local_track_id": ev.local_track_id,
                    "track_id": ev.local_track_id,
                    "global_entity_id": ev.global_entity_id,
                    "global_person_id": ev.global_entity_id,
                    "zone_id": ev.zone_id,
                    "incident_id": ev.incident_id,
                    "confidence": ev.confidence,
                    "source": ev.source,
                    "payload": json.dumps(meta_dict),
                    "parsed_payload": meta_dict,
                    "metadata": meta_dict,
                })
            return output

        if session is not None:
            return await _exec(session)

        factory = get_session_factory()
        async with factory() as local_session:
            return await _exec(local_session)

    async def get_alerts(
        self,
        camera_id: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 100,
        session: Optional[AsyncSession] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve stored alert events with filtering."""
        query = select(Event, column("rowid").label("seq_id")).where(Event.event_type == "ALERT")
        if camera_id is not None:
            query = query.where(Event.camera_id == camera_id)
        query = query.order_by(Event.timestamp.desc(), column("rowid").desc()).limit(limit)

        async def _exec(s: AsyncSession) -> List[Dict[str, Any]]:
            result = await s.execute(query)
            rows = result.all()
            alerts = []
            for r in rows:
                ev = r.Event
                meta_dict = ev.meta if isinstance(ev.meta, dict) else (
                    json.loads(ev.meta) if isinstance(ev.meta, str) and ev.meta else {}
                )
                sev_val = meta_dict.get("severity") or meta_dict.get("zone_severity")
                if severity:
                    if str(sev_val or "").upper() != severity.upper():
                        continue
                item = {
                    "seq_id": int(r.seq_id),
                    "event_id": ev.event_id,
                    "timestamp": ev.timestamp.isoformat(),
                    "camera_id": ev.camera_id,
                    "local_track_id": ev.local_track_id,
                    "track_id": ev.local_track_id,
                    "global_entity_id": ev.global_entity_id,
                    "global_person_id": ev.global_entity_id,
                    "incident_id": ev.incident_id,
                    "confidence": ev.confidence,
                    "source": ev.source,
                    "payload": json.dumps(meta_dict),
                    "parsed_payload": meta_dict,
                    "metadata": meta_dict,
                    "message": meta_dict.get("message") or meta_dict.get("narrative"),
                    "severity": sev_val,
                    "is_acknowledged": bool(meta_dict.get("is_acknowledged", False)),
                }
                alerts.append(item)
            return alerts

        if session is not None:
            return await _exec(session)

        factory = get_session_factory()
        async with factory() as local_session:
            return await _exec(local_session)

    async def get_system_stats(self, session: Optional[AsyncSession] = None) -> Dict[str, Any]:
        """Compute high-level event counts and database metrics."""
        now = time.perf_counter()
        cached = self._stats_cache
        if cached is not None and (now - cached[0]) < self._stats_cache_ttl:
            return cached[1]

        async def _exec(s: AsyncSession) -> Dict[str, Any]:
            total_events_query = select(func.count(Event.event_id))
            alerts_query = select(func.count(Event.event_id)).where(Event.event_type == "ALERT")
            cameras_query = select(func.count(func.distinct(Event.camera_id)))

            total_events = (await s.execute(total_events_query)).scalar() or 0
            total_alerts = (await s.execute(alerts_query)).scalar() or 0
            active_cameras = (await s.execute(cameras_query)).scalar() or 0

            return {
                "total_events": total_events,
                "total_alerts": total_alerts,
                "distinct_cameras_logged": active_cameras,
            }

        if session is not None:
            stats = await _exec(session)
        else:
            factory = get_session_factory()
            async with factory() as local_session:
                stats = await _exec(local_session)

        self._stats_cache = (now, stats)
        return stats

    async def acknowledge_alert(self, event_id: str, session: Optional[AsyncSession] = None) -> bool:
        """Mark an alert event as acknowledged by updating its meta JSON."""
        clean_id = str(event_id).strip()

        async def _exec(s: AsyncSession) -> bool:
            stmt = select(Event).where(Event.event_id == clean_id)
            res = await s.execute(stmt)
            row = res.scalar_one_or_none()
            if not row:
                return False
            try:
                meta_dict = dict(row.meta or {})
                meta_dict["is_acknowledged"] = True
                row.meta = meta_dict
                await s.commit()
                return True
            except Exception:
                return False

        if session is not None:
            return await _exec(session)

        factory = get_session_factory()
        async with factory() as local_session:
            return await _exec(local_session)

    async def get_incidents(
        self,
        camera_id: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50,
        session: Optional[AsyncSession] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve aggregated incidents list."""
        query = (
            select(
                Event.incident_id,
                Event.camera_id,
                func.count(column("rowid")).label("total_events"),
                func.min(Event.timestamp).label("first_seen"),
                func.max(Event.timestamp).label("last_seen"),
            )
            .where(Event.incident_id.isnot(None))
        )
        if camera_id is not None:
            query = query.where(Event.camera_id == camera_id)
        query = (
            query.group_by(Event.incident_id, Event.camera_id)
            .order_by(func.max(Event.timestamp).desc())
            .limit(limit)
        )

        async def _exec(s: AsyncSession) -> List[Dict[str, Any]]:
            res = await s.execute(query)
            rows = res.all()
            return [
                {
                    "incident_id": r.incident_id,
                    "camera_id": r.camera_id,
                    "total_events": r.total_events,
                    "first_seen": r.first_seen.isoformat() if r.first_seen else None,
                    "last_seen": r.last_seen.isoformat() if r.last_seen else None,
                    "status": "opened",
                }
                for r in rows
            ]

        if session is not None:
            return await _exec(session)

        factory = get_session_factory()
        async with factory() as local_session:
            return await _exec(local_session)


global_event_store = EventStore()


def get_event_store() -> EventStore:
    return global_event_store
