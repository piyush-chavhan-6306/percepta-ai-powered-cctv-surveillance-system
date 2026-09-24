"""
PERCEPTA Defense — Incident Engine, Alert Deduplication, Target-Specific Evidence & Timeline.

Enforces:
- Phase 13: Incident Lifecycle (DETECTED -> ACTIVE -> ESCALATED -> DE-ESCALATED -> RESOLVED)
- Phase 14: ONE INCIDENT = ONE OPERATOR ALERT (Backend alert deduplication)
- Phase 15: Target-Specific Evidence (only primary targets are attached as incident evidence)
- Phase 16: Complete Chronological Incident Timeline (What, Who, Where, When, How Serious, Why, Evidence, Status, Where Now)
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_session_factory
from backend.database.schema import Incident, Alert, Event, Evidence, GlobalEntity, LocalTrack
from backend.contracts import IncidentStatus, AlertSeverity, AlertStatus, EvidenceType

logger = logging.getLogger(__name__)


class IncidentManager:
    """
    Central manager for surveillance incidents, alert deduplication,
    target-specific evidence, and incident timelines.
    """

    def __init__(self, correlation_window_seconds: float = 120.0) -> None:
        self.correlation_window_seconds = correlation_window_seconds

        # In-memory metrics for telemetry and killer alert testing
        self.metrics = {
            "raw_events_processed": 0,
            "incidents_created": 0,
            "incidents_updated": 0,
            "alerts_emitted": 0,
            "duplicate_alerts_suppressed": 0,
        }

    @property
    def deduplication_rate_pct(self) -> float:
        """Percentage of potential duplicate alerts suppressed."""
        total = self.metrics["alerts_emitted"] + self.metrics["duplicate_alerts_suppressed"]
        if total == 0:
            return 100.0
        return round((self.metrics["duplicate_alerts_suppressed"] / total) * 100.0, 2)

    async def find_active_incident(
        self,
        camera_id: str,
        global_entity_id: Optional[str] = None,
        local_track_id: Optional[str] = None,
        zone_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> Optional[Incident]:
        """
        Find an existing active incident matching the target, camera, or zone
        within the correlation window.
        """
        now = timestamp or datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=self.correlation_window_seconds)

        factory = get_session_factory()
        async with factory() as session:
            # Look for active/escalated incidents
            active_statuses = [
                IncidentStatus.DETECTED.value,
                "ACTIVE",
                IncidentStatus.CONFIRMED.value,
                IncidentStatus.ESCALATED.value,
            ]

            # Primary match: strictly by global entity ID
            if global_entity_id:
                stmt = select(Incident).where(
                    and_(
                        Incident.primary_entity_id == global_entity_id,
                        Incident.status.in_(active_statuses),
                        Incident.last_seen >= cutoff,
                    )
                ).order_by(Incident.updated_at.desc())
                res = await session.execute(stmt)
                return res.scalars().first()

            # Secondary match: strictly by local track
            if local_track_id:
                stmt = select(Incident).where(
                    and_(
                        Incident.primary_camera_id == camera_id,
                        Incident.status.in_(active_statuses),
                        Incident.last_seen >= cutoff,
                    )
                ).order_by(Incident.updated_at.desc())
                res = await session.execute(stmt)
                for inc in res.scalars().all():
                    meta = inc.meta or {}
                    if meta.get("local_track_id") == str(local_track_id):
                        return inc
                return None

            # Fallback: by zone and camera ONLY if no specific entity was targeted
            if zone_id:
                stmt = select(Incident).where(
                    and_(
                        Incident.zone_id == zone_id,
                        Incident.primary_camera_id == camera_id,
                        Incident.primary_entity_id.is_(None),
                        Incident.status.in_(active_statuses),
                        Incident.last_seen >= cutoff,
                    )
                ).order_by(Incident.updated_at.desc())
                res = await session.execute(stmt)
                return res.scalars().first()

            return None

    async def process_event(
        self,
        event_type: str,
        camera_id: str,
        threat_score: float = 0.0,
        threat_level: str = "NORMAL",
        threat_reasons: Optional[List[str]] = None,
        global_entity_id: Optional[str] = None,
        local_track_id: Optional[str] = None,
        zone_id: Optional[str] = None,
        zone_name: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        narrative: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Incident, Optional[Alert], bool]:
        """
        Ingests an intelligence event and maps it into an Incident.
        Enforces:
        - ONE INCIDENT = ONE OPERATOR ALERT.
        - Suppresses duplicate alert spam when continuing intrusion is active.
        - Escalates or de-escalates existing incident threat.
        Returns (incident, alert, is_new_alert).
        """
        now = timestamp or datetime.now(timezone.utc)
        self.metrics["raw_events_processed"] += 1

        factory = get_session_factory()
        async with factory() as session:
            # 1. Search for existing active incident for this target
            existing_inc = await self.find_active_incident(
                camera_id=camera_id,
                global_entity_id=global_entity_id,
                local_track_id=local_track_id,
                zone_id=zone_id,
                timestamp=now,
            )

            if existing_inc:
                # Merge into existing incident
                inc = await session.get(Incident, existing_inc.incident_id)
                inc.last_seen = now
                inc.updated_at = now
                inc.current_threat = threat_score
                if threat_score > inc.peak_threat:
                    inc.peak_threat = threat_score

                # Lifecycle escalation: if threat enters high/critical band, escalate
                if threat_score >= 70.0 and inc.status != IncidentStatus.ESCALATED.value:
                    inc.status = IncidentStatus.ESCALATED.value
                    inc.severity = "CRITICAL" if threat_score >= 85.0 else "HIGH"
                elif inc.status == IncidentStatus.DETECTED.value:
                    inc.status = "ACTIVE"

                if threat_reasons:
                    old_reasons = (inc.meta or {}).get("threat_reasons", [])
                    combined = list(dict.fromkeys(old_reasons + threat_reasons))
                    inc.meta = {**(inc.meta or {}), "threat_reasons": combined, "last_narrative": narrative}

                self.metrics["incidents_updated"] += 1

                # Alert Deduplication: Find existing alert
                alert_stmt = select(Alert).where(Alert.incident_id == inc.incident_id)
                alert_res = await session.execute(alert_stmt)
                existing_alert = alert_res.scalars().first()

                if existing_alert:
                    # Update existing alert severity/message instead of creating a new one!
                    self.metrics["duplicate_alerts_suppressed"] += 1
                    if threat_score >= 70.0 and existing_alert.operator_severity != "CRITICAL":
                        existing_alert.operator_severity = "CRITICAL" if threat_score >= 85.0 else "HIGH"
                    if narrative:
                        existing_alert.message = f"[{inc.status}] {narrative} (Threat: {threat_score:.0f})"
                    existing_alert.updated_at = now
                    await session.commit()
                    return inc, existing_alert, False
                else:
                    # Incident had no alert yet (e.g. threat was previously nominal), emit first alert
                    op_sev = (
                        "CRITICAL" if threat_score >= 85.0
                        else ("HIGH" if threat_score >= 70.0
                        else ("MEDIUM" if threat_score >= 50.0
                        else ("LOW" if threat_score >= 30.0 else "NORMAL")))
                    )
                    new_alert = Alert(
                        alert_id=str(uuid.uuid4()),
                        incident_id=inc.incident_id,
                        operator_severity=op_sev,
                        operator_status="ACTIVE",
                        message=narrative or f"Security incident {inc.incident_type} in {zone_name or camera_id}",
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(new_alert)
                    self.metrics["alerts_emitted"] += 1
                    await session.commit()
                    return inc, new_alert, True

            # 2. No active incident exists -> create a brand new Incident
            inc_id = str(uuid.uuid4())
            initial_status = IncidentStatus.ESCALATED.value if threat_score >= 70.0 else IncidentStatus.DETECTED.value
            initial_sev = (
                "CRITICAL" if threat_score >= 85.0
                else ("HIGH" if threat_score >= 70.0
                else ("MEDIUM" if threat_score >= 50.0
                else ("LOW" if threat_score >= 30.0 else "NORMAL")))
            )

            meta = {
                "threat_reasons": threat_reasons or [],
                "zone_name": zone_name,
                "first_narrative": narrative,
                **(metadata or {}),
            }

            inc = Incident(
                incident_id=inc_id,
                incident_type=event_type,
                status=initial_status,
                severity=initial_sev,
                created_at=now,
                updated_at=now,
                entry_time=now,
                last_seen=now,
                peak_threat=threat_score,
                current_threat=threat_score,
                primary_entity_id=global_entity_id,
                primary_camera_id=camera_id,
                zone_id=zone_id,
                reason=narrative or f"Incident triggered by {event_type} on {camera_id}",
                meta=meta,
            )
            session.add(inc)
            self.metrics["incidents_created"] += 1

            # Create ONE Operator Alert if threat is meaningful
            new_alert = None
            if threat_score >= 30.0 or "intrusion" in event_type.lower() or "breach" in event_type.lower() or "weapon" in event_type.lower():
                op_sev = "CRITICAL" if threat_score >= 85.0 else ("HIGH" if threat_score >= 70.0 else "MEDIUM")
                new_alert = Alert(
                    alert_id=str(uuid.uuid4()),
                    incident_id=inc_id,
                    operator_severity=op_sev,
                    operator_status="ACTIVE",
                    message=narrative or f"SECURITY ALERT: {event_type} on {camera_id}",
                    created_at=now,
                    updated_at=now,
                )
                session.add(new_alert)
                self.metrics["alerts_emitted"] += 1

            await session.commit()
            return inc, new_alert, (new_alert is not None)

    async def acknowledge_incident(
        self,
        incident_id: str,
        acknowledged_by: str = "Operator",
    ) -> Optional[Incident]:
        """Operator acknowledges an incident."""
        now = datetime.now(timezone.utc)
        factory = get_session_factory()
        async with factory() as session:
            inc = await session.get(Incident, incident_id)
            if not inc:
                return None
            inc.status = IncidentStatus.ACKNOWLEDGED.value
            inc.updated_at = now
            meta = dict(inc.meta or {})
            meta["acknowledged_by"] = acknowledged_by
            meta["acknowledged_at"] = now.isoformat()
            inc.meta = meta

            # Acknowledge linked alert
            alert_stmt = select(Alert).where(Alert.incident_id == incident_id)
            res = await session.execute(alert_stmt)
            for alert in res.scalars().all():
                alert.is_acknowledged = True
                alert.acknowledged_at = now
                alert.acknowledged_by = acknowledged_by
                alert.operator_status = AlertStatus.ACKNOWLEDGED.value

            await session.commit()
            logger.info(f"IncidentManager: Incident {incident_id} acknowledged by {acknowledged_by}")
            return inc

    async def resolve_incident(
        self,
        incident_id: str,
        resolved_by: str = "Operator",
        resolution_notes: str = "Situation normalized",
    ) -> Optional[Incident]:
        """Operator or automated de-escalation resolves an incident."""
        now = datetime.now(timezone.utc)
        factory = get_session_factory()
        async with factory() as session:
            inc = await session.get(Incident, incident_id)
            if not inc:
                return None
            inc.status = IncidentStatus.RESOLVED.value
            inc.resolved_at = now
            inc.exit_time = now
            inc.updated_at = now
            if inc.entry_time:
                entry = inc.entry_time
                if entry.tzinfo is None:
                    entry = entry.replace(tzinfo=timezone.utc)
                inc.duration_seconds = max(0.0, (now - entry).total_seconds())

            meta = dict(inc.meta or {})
            meta["resolved_by"] = resolved_by
            meta["resolution_notes"] = resolution_notes
            inc.meta = meta

            # Resolve linked alert
            alert_stmt = select(Alert).where(Alert.incident_id == incident_id)
            res = await session.execute(alert_stmt)
            for alert in res.scalars().all():
                alert.operator_status = AlertStatus.RESOLVED.value
                alert.updated_at = now

            await session.commit()
            logger.info(f"IncidentManager: Incident {incident_id} resolved by {resolved_by}")
            return inc

    async def attach_target_evidence(
        self,
        incident_id: str,
        target_entity_id: Optional[str],
        camera_id: str,
        evidence_type: str,
        target_bbox: Optional[List[float]] = None,
        target_crop_path: Optional[str] = None,
        full_scene_path: Optional[str] = None,
        confidence: float = 1.0,
        quality: float = 1.0,
        reason: str = "Target evidence captured",
        local_track_id: Optional[str] = None,
        session_id: Optional[str] = None,
        frame_number: Optional[int] = None,
        timestamp: Optional[datetime] = None,
    ) -> Optional[Evidence]:
        """
        Phase 15: Target-Specific Evidence.
        CRITICAL RULE: If 7 people are visible, ONLY the primary target is marked as incident evidence!
        Rejects attaching non-target bystander evidence.
        """
        now = timestamp or datetime.now(timezone.utc)
        factory = get_session_factory()
        async with factory() as session:
            inc = await session.get(Incident, incident_id)
            if not inc:
                logger.warning(f"attach_target_evidence: Incident {incident_id} not found")
                return None

            # Enforce target specificity: target must match primary entity if specified
            if inc.primary_entity_id and target_entity_id:
                if inc.primary_entity_id != target_entity_id:
                    logger.warning(
                        f"attach_target_evidence: Rejected evidence for entity {target_entity_id}; "
                        f"does not match incident primary target {inc.primary_entity_id}"
                    )
                    return None

            # Compute tamper-evident SHA-256 from ACTUAL file content when possible,
            # fall back to metadata-based hash when no file path is provided.
            sha_hash = None
            evidence_file = target_crop_path or full_scene_path
            if evidence_file:
                try:
                    import os
                    from pathlib import Path as _P
                    fpath = _P(evidence_file)
                    if fpath.exists() and fpath.stat().st_size > 0:
                        h = hashlib.sha256()
                        with open(fpath, "rb") as fh:
                            for chunk in iter(lambda: fh.read(65536), b""):
                                h.update(chunk)
                        sha_hash = h.hexdigest()
                except Exception as hash_err:
                    logger.debug(f"File SHA-256 failed for {evidence_file}: {hash_err}")
            if not sha_hash:
                token_src = f"{incident_id}:{target_entity_id}:{camera_id}:{now.isoformat()}:{reason}"
                sha_hash = hashlib.sha256(token_src.encode("utf-8")).hexdigest()

            ev = Evidence(
                evidence_id=str(uuid.uuid4()),
                incident_id=incident_id,
                global_entity_id=target_entity_id,
                local_track_id=local_track_id,
                camera_id=camera_id,
                session_id=session_id,
                timestamp=now,
                evidence_type=evidence_type,
                source_frame_number=frame_number,
                target_bbox=target_bbox,
                target_crop_path=target_crop_path,
                full_scene_path=full_scene_path,
                confidence=confidence,
                quality=quality,
                reason=reason,
                sha256_hash=sha_hash,
                meta={"target_verified": True, "hash_source": "file" if evidence_file else "metadata"},
            )
            session.add(ev)
            await session.commit()
            logger.info(f"Target evidence {ev.evidence_id} ({evidence_type}) attached to incident {incident_id}")
            return ev

    async def get_incident_timeline(self, incident_id: str) -> Dict[str, Any]:
        """
        Phase 16: Complete Chronological Incident Timeline.
        Answers:
        WHAT? (incident_type, summary)
        WHO? (primary_entity_id, target class)
        WHERE? (primary_camera, zone)
        WHEN? (entry_time, last_seen, duration)
        HOW SERIOUS? (peak_threat, current_threat, severity)
        WHY? (threat reasons, causal chain)
        EVIDENCE? (target-specific evidence items, sha256 hashes)
        STATUS? (DETECTED, ACTIVE, ESCALATED, RESOLVED)
        WHERE NOW? (target current camera and track)
        """
        factory = get_session_factory()
        async with factory() as session:
            inc = await session.get(Incident, incident_id)
            if not inc:
                return {}

            # Fetch linked events
            events_stmt = select(Event).where(Event.incident_id == incident_id).order_by(Event.timestamp.asc())
            events_res = await session.execute(events_stmt)
            raw_events = events_res.scalars().all()

            # Fetch linked target evidence
            ev_stmt = select(Evidence).where(Evidence.incident_id == incident_id).order_by(Evidence.timestamp.asc())
            ev_res = await session.execute(ev_stmt)
            evidence_items = ev_res.scalars().all()

            # Fetch linked alerts
            alert_stmt = select(Alert).where(Alert.incident_id == incident_id)
            alert_res = await session.execute(alert_stmt)
            alerts = alert_res.scalars().all()

            # Target current status
            target_now = None
            if inc.primary_entity_id:
                ent = await session.get(GlobalEntity, inc.primary_entity_id)
                if ent:
                    target_now = {
                        "display_id": ent.display_id,
                        "current_camera": ent.current_camera_id,
                        "current_local_track": ent.current_local_track_id,
                        "status": ent.status,
                        "last_seen": ent.last_seen.isoformat() if ent.last_seen else None,
                    }

            # Build unified chronological timeline items
            timeline_items = []

            # 1. Detection entry point
            timeline_items.append({
                "timestamp": inc.created_at.isoformat() if inc.created_at else None,
                "step": "ACQUISITION",
                "title": f"Target acquired on {inc.primary_camera_id}",
                "detail": f"Incident {inc.incident_type} initiated. Initial severity: {inc.severity}",
                "threat_score": inc.peak_threat,
            })

            # 2. Chronological events
            for e in raw_events:
                timeline_items.append({
                    "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                    "step": "EVENT",
                    "title": e.event_type.upper().replace("_", " "),
                    "detail": f"Observed on camera {e.camera_id} (confidence: {e.confidence or 0.0:.2f})",
                    "threat_score": inc.current_threat,
                })

            # 3. Evidence captures
            for ev in evidence_items:
                timeline_items.append({
                    "timestamp": ev.timestamp.isoformat() if ev.timestamp else None,
                    "step": "EVIDENCE",
                    "title": f"Evidence captured ({ev.evidence_type})",
                    "detail": ev.reason,
                    "crop_path": ev.target_crop_path,
                    "sha256": ev.sha256_hash,
                })

            # 4. Current status / Resolution
            if inc.status == IncidentStatus.RESOLVED.value:
                timeline_items.append({
                    "timestamp": inc.resolved_at.isoformat() if inc.resolved_at else None,
                    "step": "RESOLUTION",
                    "title": "Incident Resolved",
                    "detail": (inc.meta or {}).get("resolution_notes", "Situation normalized"),
                    "threat_score": 0.0,
                })

            return {
                "incident_id": inc.incident_id,
                "what": inc.incident_type,
                "who": inc.primary_entity_id,
                "where": inc.primary_camera_id,
                "zone_id": inc.zone_id,
                "when": {
                    "start": inc.created_at.isoformat() if inc.created_at else None,
                    "last_seen": inc.last_seen.isoformat() if inc.last_seen else None,
                    "resolved_at": inc.resolved_at.isoformat() if inc.resolved_at else None,
                    "duration_seconds": inc.duration_seconds,
                },
                "how_serious": {
                    "severity": inc.severity,
                    "peak_threat": inc.peak_threat,
                    "current_threat": inc.current_threat,
                },
                "why": (inc.meta or {}).get("threat_reasons", [inc.reason]),
                "status": inc.status,
                "where_now": target_now,
                "total_events": len(raw_events),
                "evidence_count": len(evidence_items),
                "alerts_count": len(alerts),
                "timeline": timeline_items,
            }

    def get_deduplication_metrics(self) -> Dict[str, Any]:
        """Export alert deduplication metrics."""
        return {
            "raw_events_processed": self.metrics["raw_events_processed"],
            "incidents_created": self.metrics["incidents_created"],
            "incidents_updated": self.metrics["incidents_updated"],
            "alerts_emitted": self.metrics["alerts_emitted"],
            "duplicate_alerts_suppressed": self.metrics["duplicate_alerts_suppressed"],
            "deduplication_rate_pct": self.deduplication_rate_pct,
        }


global_incident_manager = IncidentManager()


def get_incident_manager() -> IncidentManager:
    return global_incident_manager
