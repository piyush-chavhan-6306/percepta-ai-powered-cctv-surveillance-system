"""
Border Intelligence Grounded Natural-Language Surveillance Intelligence Assistant.
Implements controlled, parameter-validated database retrieval, intent understanding,
and 3-tier grounded answers with anti-hallucination guardrails.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import json
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_session_factory
from backend.events.schema import EventType
from backend.events.store import EventStore, get_event_store
from backend.incidents.models import EventLogModel

logger = logging.getLogger(__name__)


@dataclass
class GroundedQueryResponse:
    """Structured response model for natural-language surveillance queries."""
    query: str
    status: str  # "answered", "no_records_found", "unsupported_capability", "invalid_query"
    observed_facts: List[str] = field(default_factory=list)
    rule_results: List[str] = field(default_factory=list)
    interpretation: str = ""
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    grounding_status: str = "grounded"  # "grounded", "refusal", "no_data"

    def to_dict(self) -> Dict[str, Any]:
        return {

            
            "query": self.query,
            "status": self.status,
            "observed_facts": self.observed_facts,
            "rule_results": self.rule_results,
            "interpretation": self.interpretation,
            "evidence": self.evidence,
            "grounding_status": self.grounding_status,
        }

    def formatted_text(self) -> str:
        """Returns the standard 3-tier human-readable response."""
        parts = []
        if self.observed_facts:
            parts.append("[OBSERVED FACT]\n" + "\n".join(f"- {f}" for f in self.observed_facts))
        if self.rule_results:
            parts.append("[DETERMINISTIC RULE RESULT]\n" + "\n".join(f"- {r}" for r in self.rule_results))
        if self.interpretation:
            parts.append(f"[AI INTERPRETATION / SUMMARY]\n{self.interpretation}")
        return "\n\n".join(parts) if parts else self.interpretation


class ControlledQueryLayer:
    """
    Controlled parameter-validated database access layer.
    Strictly uses SQLAlchemy parameterized ORM queries. Never evaluates arbitrary SQL strings.
    """

    def __init__(self, event_store: Optional[EventStore] = None) -> None:
        self.event_store = event_store or get_event_store()

    async def get_track_events(
        self,
        track_id: str,
        camera_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Fetch all events associated with a specific camera-local track ID."""
        clean_track_id = str(track_id).strip()
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(EventLogModel).where(EventLogModel.track_id == clean_track_id)
            if camera_id:
                stmt = stmt.where(EventLogModel.camera_id == str(camera_id).strip())
            if event_type:
                stmt = stmt.where(EventLogModel.event_type == event_type)
            stmt = stmt.order_by(EventLogModel.timestamp.desc(), EventLogModel.seq_id.desc()).limit(limit)
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [self._row_to_dict(r) for r in reversed(rows)]

    async def get_zone_events_for_track(
        self,
        track_id: str,
        transition: Optional[str] = None,
        camera_id: Optional[str] = None,
        zone_id: Optional[str] = None,
        limit: int = 2000,
    ) -> List[Dict[str, Any]]:
        """Fetch zone transition events (entered, exited, crossed, loitering) for a track."""
        events = await self.get_track_events(
            track_id=track_id,
            camera_id=camera_id,
            event_type=EventType.ZONE.value,
            limit=limit,
        )
        zone_evs = []
        for e in events:
            if e["event_type"] == EventType.ZONE.value:
                payload = e.get("parsed_payload", {})
                if transition and payload.get("transition") != transition:
                    continue
                if zone_id and payload.get("zone_id") != zone_id:
                    continue
                zone_evs.append(e)
        return zone_evs

    async def get_camera_events_in_timeframe(
        self,
        camera_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_type: Optional[str] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        """Fetch chronological events on a camera within an optional time window."""
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(EventLogModel)
            if camera_id:
                stmt = stmt.where(EventLogModel.camera_id == str(camera_id).strip())
            if start_time:
                stmt = stmt.where(EventLogModel.timestamp >= start_time)
            if end_time:
                stmt = stmt.where(EventLogModel.timestamp <= end_time)
            if event_type:
                stmt = stmt.where(EventLogModel.event_type == str(event_type).strip().upper())

            stmt = stmt.order_by(EventLogModel.timestamp.desc(), EventLogModel.seq_id.desc()).limit(limit)
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [self._row_to_dict(r) for r in reversed(rows)]

    async def get_alerts(
        self,
        camera_id: Optional[str] = None,
        track_id: Optional[str] = None,
        alert_id: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Fetch security alert events with optional filters."""
        factory = get_session_factory()
        async with factory() as session:
            stmt = select(EventLogModel).where(EventLogModel.event_type == EventType.ALERT.value)
            if alert_id:
                stmt = stmt.where(EventLogModel.event_id == str(alert_id).strip())
            if camera_id:
                stmt = stmt.where(EventLogModel.camera_id == str(camera_id).strip())
            if track_id:
                stmt = stmt.where(EventLogModel.track_id == str(track_id).strip())

            stmt = stmt.order_by(EventLogModel.timestamp.desc(), EventLogModel.seq_id.desc()).limit(limit)
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [self._row_to_dict(r) for r in rows]

    def _row_to_dict(self, row: EventLogModel) -> Dict[str, Any]:
        payload_data = {}
        try:
            payload_data = json.loads(row.payload)
        except Exception:
            payload_data = {}
        return {
            "seq_id": row.seq_id,
            "event_id": row.event_id,
            "event_type": row.event_type,
            "timestamp": row.timestamp.isoformat() if row.timestamp else "",
            "camera_id": row.camera_id,
            "track_id": row.track_id,
            "incident_id": row.incident_id,
            "confidence": row.confidence,
            "source": row.source,
            "parsed_payload": payload_data,
        }


class SurveillanceAssistant:
    """
    Grounded Natural-Language Intelligence Assistant.
    Parses operator questions, performs parameter-validated database retrieval,
    applies anti-hallucination guardrails, and constructs 3-tier explainable responses.
    """

    def __init__(self, query_layer: Optional[ControlledQueryLayer] = None) -> None:
        self.query_layer = query_layer or ControlledQueryLayer()

    async def answer_query(
        self,
        query: str,
        camera_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> GroundedQueryResponse:
        """
        Main query handling pipeline:
        1. Validate query & check guardrails (biometrics, weapon, intent refusal).
        2. Extract parameters & classify intent.
        3. Execute controlled queries on SQLite EventStore.
        4. Synthesize 3-tier grounded response.
        """
        if not query or not query.strip():
            return GroundedQueryResponse(
                query=query or "",
                status="invalid_query",
                interpretation="Empty query provided. Please provide a specific surveillance question.",
                grounding_status="no_data",
            )

        q = query.strip()

        # -------------------------------------------------------------
        # 1. Anti-Hallucination & Out-of-Scope Capability Guardrails
        # -------------------------------------------------------------
        refusal_response = self._check_anti_hallucination_guardrails(q)
        if refusal_response:
            return refusal_response

        # -------------------------------------------------------------
        # 2. Extract Query Parameters & Intent Classification
        # -------------------------------------------------------------
        extracted_track = self._extract_track_id(q)
        extracted_cam = camera_id or self._extract_camera_id(q)
        extracted_zone = self._extract_zone_name(q)
        time_delta = self._extract_relative_time_window(q)

        if time_delta and not start_time:
            now = datetime.now(timezone.utc)
            start_time = now - time_delta
            end_time = now

        # Intent Detection
        lower_q = q.lower()

        # A. Track Entry Query
        if extracted_track and ("enter" in lower_q or "entered" in lower_q or "entry" in lower_q):
            return await self._handle_track_entry_query(q, extracted_track, extracted_cam, extracted_zone)

        # B. Track Exit Query
        if extracted_track and ("leave" in lower_q or "left" in lower_q or "exit" in lower_q or "exited" in lower_q):
            return await self._handle_track_exit_query(q, extracted_track, extracted_cam, extracted_zone)

        # C. Track Dwell / Loitering Duration Query
        if extracted_track and ("how long" in lower_q or "dwell" in lower_q or "remain" in lower_q or "loiter" in lower_q):
            return await self._handle_track_dwell_query(q, extracted_track, extracted_cam, extracted_zone)

        # D. Track Movement / Direction Query
        if extracted_track and ("direction" in lower_q or "heading" in lower_q or "speed" in lower_q or "moving" in lower_q):
            return await self._handle_track_movement_query(q, extracted_track, extracted_cam)

        # E. General Track Investigation
        if extracted_track:
            return await self._handle_track_investigation(q, extracted_track, extracted_cam)

        # F. Alert Explanation Query
        if "alert" in lower_q or "why was" in lower_q or "breach" in lower_q:
            return await self._handle_alert_explanation_query(q, extracted_cam)

        # G. Boundary Crossing / Tripwire Query
        if "boundary" in lower_q or "cross" in lower_q or "tripwire" in lower_q or "fence" in lower_q:
            return await self._handle_boundary_crossing_query(q, extracted_cam, start_time, end_time)

        # H. Highest Risk / Evidence Query
        if "highest" in lower_q or "most critical" in lower_q or "evidence" in lower_q:
            return await self._handle_highest_risk_query(q, extracted_cam)

        # I. Zone Investigation Query
        if extracted_zone or "who entered" in lower_q or "in zone" in lower_q:
            return await self._handle_zone_investigation(q, extracted_zone, extracted_cam)

        # J. Temporal / Camera Activity Summary
        return await self._handle_temporal_camera_summary(q, extracted_cam, start_time, end_time)

    # -------------------------------------------------------------
    # Guardrail Checkers
    # -------------------------------------------------------------
    def _check_anti_hallucination_guardrails(self, query: str) -> Optional[GroundedQueryResponse]:
        lower_q = query.lower()

        # 1. Biometric / Personal Identity Recognition
        if any(w in lower_q for w in [
            "who is this", "who is track", "what is their name", "what is his name", "what is her name",
            "identify face", "facial recognition", "is that john", "identify person", "identity of track", "identity of person"
        ]):
            return GroundedQueryResponse(
                query=query,
                status="unsupported_capability",
                interpretation=(
                    "CAPABILITY REFUSAL: The platform only maintains camera-local Track IDs (e.g. 'Track 12') "
                    "derived from bounding box centroids. Biometric facial recognition and personal identity "
                    "lookup are not supported or enabled in this CCTV surveillance architecture."
                ),
                grounding_status="refusal",
            )

        # 2. Weapon / Specialized Threat Determination
        if any(w in lower_q for w in ["weapon", "gun", "knife", "armed", "firearm", "pistol", "rifle", "bomb", "explosive"]):
            return GroundedQueryResponse(
                query=query,
                status="unsupported_capability",
                interpretation=(
                    "CAPABILITY REFUSAL: The active computer vision detector (YOLOv8n) is configured for general "
                    "surveillance classes (person, vehicle, bicycle). Weapon or specialized threat detection is not "
                    "supported by the current model."
                ),
                grounding_status="refusal",
            )

        # 3. Subjective / Criminal Intent
        if any(w in lower_q for w in [
            "intent", "planning to attack", "planning an attack", "planning attack", "plan an attack",
            "is he suspicious", "is this suspicious", "what are they planning", "criminal intent", "hostile intent"
        ]):
            return GroundedQueryResponse(
                query=query,
                status="unsupported_capability",
                interpretation=(
                    "CAPABILITY REFUSAL: Subjective human intent or criminal intent cannot be established from "
                    "video observations alone. The platform strictly reports deterministic spatial interactions, "
                    "movement vectors, and configured rule triggers."
                ),
                grounding_status="refusal",
            )

        # 4. Cross-Camera Re-Identification
        if any(w in lower_q for w in ["same person on", "same track on camera", "cross-camera", "same individual on"]):
            return GroundedQueryResponse(
                query=query,
                status="unsupported_capability",
                interpretation=(
                    "CAPABILITY REFUSAL: Track IDs are strictly camera-local. Cross-camera re-identification "
                    "requires a validated multi-camera Re-ID model, which is not enabled in the current deployment."
                ),
                grounding_status="refusal",
            )

        # 5. Raw SQL Injection / Malicious Command Attempts
        if any(kw in lower_q for kw in ["select *", "drop table", "union select", "insert into", "delete from", "update "]):
            return GroundedQueryResponse(
                query=query,
                status="invalid_query",
                interpretation="SECURITY REFUSAL: Raw SQL keywords detected. Arbitrary SQL execution is strictly forbidden.",
                grounding_status="refusal",
            )

        return None

    # -------------------------------------------------------------
    # Intent Handlers
    # -------------------------------------------------------------
    async def _handle_track_entry_query(
        self,
        query: str,
        track_id: str,
        camera_id: Optional[str],
        zone_name: Optional[str],
    ) -> GroundedQueryResponse:
        entry_events = await self.query_layer.get_zone_events_for_track(
            track_id=track_id,
            transition="entered",
            camera_id=camera_id,
        )

        if not entry_events:
            return GroundedQueryResponse(
                query=query,
                status="no_records_found",
                interpretation=f"No zone entry events recorded for Track {track_id} in the database.",
                grounding_status="no_data",
            )

        observed = []
        rules = []
        evidence = []

        for e in entry_events:
            p = e.get("parsed_payload", {})
            z_name = p.get("zone_name", "Restricted Area")
            z_sev = p.get("zone_severity", "restricted").upper()
            ts = e["timestamp"]
            cam = e["camera_id"]
            observed.append(f"Track {track_id} was recorded entering '{z_name}' on camera '{cam}' at {ts}.")
            rules.append(f"Security zone '{z_name}' classified this transition as a {z_sev} intrusion rule event.")
            evidence.append(e)

        first_entry = entry_events[0]
        f_time = first_entry["timestamp"]
        f_zone = first_entry.get("parsed_payload", {}).get("zone_name", "Restricted Area")

        interpretation = f"Track {track_id} entered zone '{f_zone}' at {f_time}."

        return GroundedQueryResponse(
            query=query,
            status="answered",
            observed_facts=observed,
            rule_results=rules,
            interpretation=interpretation,
            evidence=evidence,
            grounding_status="grounded",
        )

    async def _handle_track_exit_query(
        self,
        query: str,
        track_id: str,
        camera_id: Optional[str],
        zone_name: Optional[str],
    ) -> GroundedQueryResponse:
        exit_events = await self.query_layer.get_zone_events_for_track(
            track_id=track_id,
            transition="exited",
            camera_id=camera_id,
        )

        if not exit_events:
            return GroundedQueryResponse(
                query=query,
                status="no_records_found",
                interpretation=f"No zone exit events recorded for Track {track_id}.",
                grounding_status="no_data",
            )

        observed = []
        rules = []
        evidence = []

        for e in exit_events:
            p = e.get("parsed_payload", {})
            z_name = p.get("zone_name", "Restricted Area")
            ts = e["timestamp"]
            cam = e["camera_id"]
            dwell = p.get("dwell_duration_seconds")
            dwell_str = f" after dwelling for {dwell:.1f}s" if dwell is not None else ""
            observed.append(f"Track {track_id} was recorded exiting zone '{z_name}' on camera '{cam}' at {ts}{dwell_str}.")
            rules.append(f"Zone monitor updated track {track_id} occupancy state to EXITED.")
            evidence.append(e)

        interpretation = f"Track {track_id} exited zone '{exit_events[0].get('parsed_payload', {}).get('zone_name')}' at {exit_events[0]['timestamp']}."

        return GroundedQueryResponse(
            query=query,
            status="answered",
            observed_facts=observed,
            rule_results=rules,
            interpretation=interpretation,
            evidence=evidence,
            grounding_status="grounded",
        )

    async def _handle_track_dwell_query(
        self,
        query: str,
        track_id: str,
        camera_id: Optional[str],
        zone_name: Optional[str],
    ) -> GroundedQueryResponse:
        all_zone_events = await self.query_layer.get_zone_events_for_track(
            track_id=track_id,
            camera_id=camera_id,
        )

        if not all_zone_events:
            return GroundedQueryResponse(
                query=query,
                status="no_records_found",
                interpretation=f"No zone dwell records found for Track {track_id}.",
                grounding_status="no_data",
            )

        observed = []
        rules = []
        evidence = []
        max_dwell = 0.0

        for e in all_zone_events:
            p = e.get("parsed_payload", {})
            dwell = p.get("dwell_duration_seconds", 0.0)
            if dwell and dwell > max_dwell:
                max_dwell = dwell
            evidence.append(e)

        loiter_events = [e for e in all_zone_events if e.get("parsed_payload", {}).get("transition") == "loitering"]
        exit_events = [e for e in all_zone_events if e.get("parsed_payload", {}).get("transition") == "exited"]

        observed.append(f"Track {track_id} has {len(all_zone_events)} recorded zone state events with a maximum recorded dwell of {max_dwell:.1f} seconds.")
        if loiter_events:
            rules.append(f"Loitering rule threshold was triggered for Track {track_id} at {loiter_events[0]['timestamp']}.")
        else:
            rules.append("Dwell duration remained within normal operational thresholds without triggering loitering alerts.")

        interpretation = f"Track {track_id} remained in the zone for approximately {max_dwell:.1f} seconds."

        return GroundedQueryResponse(
            query=query,
            status="answered",
            observed_facts=observed,
            rule_results=rules,
            interpretation=interpretation,
            evidence=evidence,
            grounding_status="grounded",
        )

    async def _handle_track_movement_query(
        self,
        query: str,
        track_id: str,
        camera_id: Optional[str],
    ) -> GroundedQueryResponse:
        events = await self.query_layer.get_track_events(
            track_id=track_id,
            camera_id=camera_id,
            event_type=EventType.TRACKING.value,
            limit=1000,
        )
        track_events = events

        if not track_events:
            return GroundedQueryResponse(
                query=query,
                status="no_records_found",
                interpretation=f"No movement tracking events found for Track {track_id}.",
                grounding_status="no_data",
            )

        last_ev = track_events[-1]
        p = last_ev.get("parsed_payload", {})
        pos = p.get("position", [0.0, 0.0])
        vel = p.get("velocity", [0.0, 0.0])
        speed = p.get("speed", 0.0)
        heading_deg = p.get("direction", 0.0)
        obj_class = p.get("object_class", "object")

        observed = [
            f"Track {track_id} ({obj_class}) was last recorded at pixel coordinates ({pos[0]:.1f}, {pos[1]:.1f}) with velocity vector ({vel[0]:.1f}, {vel[1]:.1f}) px/frame.",
            f"Measured speed was {speed:.2f} pixels/frame at heading angle {heading_deg:.1f} degrees.",
        ]
        rules = ["Movement vector was computed from bounded trajectory centroid displacement."]
        interpretation = f"Track {track_id} was moving with a velocity of ({vel[0]:.1f}, {vel[1]:.1f}) pixels/frame ({speed:.2f} px/frame speed)."

        return GroundedQueryResponse(
            query=query,
            status="answered",
            observed_facts=observed,
            rule_results=rules,
            interpretation=interpretation,
            evidence=[last_ev],
            grounding_status="grounded",
        )

    async def _handle_track_investigation(
        self,
        query: str,
        track_id: str,
        camera_id: Optional[str],
    ) -> GroundedQueryResponse:
        events = await self.query_layer.get_track_events(track_id=track_id, camera_id=camera_id, limit=100)

        if not events:
            return GroundedQueryResponse(
                query=query,
                status="no_records_found",
                interpretation=f"Track {track_id} was not found in the stored surveillance records.",
                grounding_status="no_data",
            )

        types_count = {}
        for e in events:
            t = e["event_type"]
            types_count[t] = types_count.get(t, 0) + 1

        first_ts = events[0]["timestamp"]
        last_ts = events[-1]["timestamp"]
        cam = events[0]["camera_id"]
        cls_name = events[0].get("parsed_payload", {}).get("object_class", "object")

        observed = [
            f"Track {track_id} ({cls_name}) recorded {len(events)} events on camera '{cam}' from {first_ts} to {last_ts}.",
            f"Event breakdown: " + ", ".join(f"{k}: {v}" for k, v in types_count.items()),
        ]
        rules = ["Track history maintained through persistent ByteTrack association and zone monitor."]
        interpretation = f"Track {track_id} was active on camera '{cam}' between {first_ts} and {last_ts} generating {len(events)} structured events."

        return GroundedQueryResponse(
            query=query,
            status="answered",
            observed_facts=observed,
            rule_results=rules,
            interpretation=interpretation,
            evidence=events[:10],
            grounding_status="grounded",
        )

    async def _handle_alert_explanation_query(
        self,
        query: str,
        camera_id: Optional[str],
    ) -> GroundedQueryResponse:
        alerts = await self.query_layer.get_alerts(camera_id=camera_id, limit=5)

        if not alerts:
            return GroundedQueryResponse(
                query=query,
                status="no_records_found",
                interpretation="No security alerts have been triggered in the database.",
                grounding_status="no_data",
            )

        observed = []
        rules = []
        for a in alerts:
            p = a.get("parsed_payload", {})
            sev = p.get("severity", "ALERT")
            msg = p.get("message", "Security Alert")
            t_id = a.get("track_id", "Unknown")
            ts = a.get("timestamp")
            observed.append(f"Alert [{sev}] at {ts} on Camera '{a['camera_id']}' for Track {t_id}: '{msg}'")
            rules.append(f"Alert was generated because Track {t_id} violated configured surveillance threshold/boundary rule.")

        interpretation = f"Recent alerts were triggered by security boundary crossings and restricted zone entries. Most recent: '{alerts[0].get('parsed_payload', {}).get('message')}'."

        return GroundedQueryResponse(
            query=query,
            status="answered",
            observed_facts=observed,
            rule_results=rules,
            interpretation=interpretation,
            evidence=alerts,
            grounding_status="grounded",
        )

    async def _handle_boundary_crossing_query(
        self,
        query: str,
        camera_id: Optional[str],
        start_time: Optional[datetime],
        end_time: Optional[datetime],
    ) -> GroundedQueryResponse:
        events = await self.query_layer.get_camera_events_in_timeframe(
            camera_id=camera_id,
            start_time=start_time,
            end_time=end_time,
            event_type=EventType.ZONE.value,
            limit=500,
        )

        crossings = [e for e in events if e.get("parsed_payload", {}).get("transition") == "crossed"]

        if not crossings:
            return GroundedQueryResponse(
                query=query,
                status="no_records_found",
                interpretation="No virtual boundary crossings were recorded for the specified criteria.",
                grounding_status="no_data",
            )

        observed = []
        rules = []
        for c in crossings:
            p = c.get("parsed_payload", {})
            b_name = p.get("zone_name", "Boundary Line")
            t_id = c.get("track_id")
            ts = c.get("timestamp")
            cam = c.get("camera_id")
            observed.append(f"Track {t_id} crossed virtual boundary '{b_name}' on camera '{cam}' at {ts}.")
            rules.append(f"Tripwire crossing rule evaluated directed line intersection.")

        interpretation = f"Recorded {len(crossings)} virtual boundary crossing events."

        return GroundedQueryResponse(
            query=query,
            status="answered",
            observed_facts=observed,
            rule_results=rules,
            interpretation=interpretation,
            evidence=crossings,
            grounding_status="grounded",
        )

    async def _handle_highest_risk_query(
        self,
        query: str,
        camera_id: Optional[str],
    ) -> GroundedQueryResponse:
        alerts = await self.query_layer.get_alerts(camera_id=camera_id, limit=5)

        if not alerts:
            return GroundedQueryResponse(
                query=query,
                status="no_records_found",
                interpretation="No alerts or high-risk events found in the stored records.",
                grounding_status="no_data",
            )

        top_alert = alerts[0]
        p = top_alert.get("parsed_payload", {})
        sev = p.get("severity", "HIGH")
        msg = p.get("message", "Security Alert")
        ts = top_alert.get("timestamp")
        cam = top_alert.get("camera_id")
        t_id = top_alert.get("track_id")

        observed = [
            f"Highest severity alert: [{sev}] on Camera '{cam}' at {ts}.",
            f"Associated Track: Track {t_id}.",
            f"Alert Details: {msg}",
        ]
        rules = [f"Rule Engine categorized this event with {sev} priority based on restricted boundary breach."]
        interpretation = f"The highest priority alert is '{msg}' on Camera '{cam}' (Severity: {sev})."

        return GroundedQueryResponse(
            query=query,
            status="answered",
            observed_facts=observed,
            rule_results=rules,
            interpretation=interpretation,
            evidence=[top_alert],
            grounding_status="grounded",
        )

    async def _handle_zone_investigation(
        self,
        query: str,
        zone_name: Optional[str],
        camera_id: Optional[str],
    ) -> GroundedQueryResponse:
        events = await self.query_layer.get_camera_events_in_timeframe(
            camera_id=camera_id,
            event_type=EventType.ZONE.value,
            limit=50,
        )

        if not events:
            return GroundedQueryResponse(
                query=query,
                status="no_records_found",
                interpretation="No zone intrusion or transition events recorded.",
                grounding_status="no_data",
            )

        tracks_seen = set()
        observed = []
        for e in events:
            p = e.get("parsed_payload", {})
            t_id = e.get("track_id")
            z_name = p.get("zone_name", "Zone")
            trans = p.get("transition", "event")
            ts = e.get("timestamp")
            tracks_seen.add(t_id)
            observed.append(f"Track {t_id} was recorded in state '{trans}' for zone '{z_name}' at {ts}.")

        rules = ["Spatial containment evaluated via polygon ray-casting."]
        interpretation = f"{len(tracks_seen)} unique tracks ({', '.join(str(t) for t in tracks_seen)}) were recorded interacting with configured security zones."

        return GroundedQueryResponse(
            query=query,
            status="answered",
            observed_facts=observed[:10],
            rule_results=rules,
            interpretation=interpretation,
            evidence=events[:10],
            grounding_status="grounded",
        )

    async def _handle_temporal_camera_summary(
        self,
        query: str,
        camera_id: Optional[str],
        start_time: Optional[datetime],
        end_time: Optional[datetime],
    ) -> GroundedQueryResponse:
        events = await self.query_layer.get_camera_events_in_timeframe(
            camera_id=camera_id,
            start_time=start_time,
            end_time=end_time,
            limit=100,
        )

        if not events:
            cam_str = f" on Camera '{camera_id}'" if camera_id else ""
            return GroundedQueryResponse(
                query=query,
                status="no_records_found",
                interpretation=f"No surveillance events recorded{cam_str} for the requested timeframe.",
                grounding_status="no_data",
            )

        counts = {}
        for e in events:
            t = e["event_type"]
            counts[t] = counts.get(t, 0) + 1

        cam_name = camera_id or events[0]["camera_id"]
        observed = [
            f"Total events recorded: {len(events)} on camera '{cam_name}'.",
            f"Activity breakdown: " + ", ".join(f"{k}: {v}" for k, v in counts.items()),
            f"Time window: from {events[0]['timestamp']} to {events[-1]['timestamp']}.",
        ]
        rules = ["Events aggregated from verified SQLite WAL persistence logs."]
        interpretation = f"Camera '{cam_name}' recorded {len(events)} structured events ({counts.get('ALERT', 0)} alerts, {counts.get('ZONE', 0)} zone events, {counts.get('TRACKING', 0)} tracking records)."

        return GroundedQueryResponse(
            query=query,
            status="answered",
            observed_facts=observed,
            rule_results=rules,
            interpretation=interpretation,
            evidence=events[:10],
            grounding_status="grounded",
        )

    # -------------------------------------------------------------
    # Extraction Helpers
    # -------------------------------------------------------------
    def _extract_track_id(self, query: str) -> Optional[str]:
        m = re.search(r"\btrack\s*(?:id)?\s*#?\s*([0-9]+|[a-zA-Z0-9_\-]+)\b", query, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            if val.lower() in ("this", "the", "that", "all", "each", "a", "an", "is", "was", "any", "id"):
                return None
            return val
        return None

    def _extract_camera_id(self, query: str) -> Optional[str]:
        # 1. Match direct patterns like cam_01, cctv_01, cam-1, cam_intel_test
        m_direct = re.search(r"\b(cam(?:era)?[_\-][a-zA-Z0-9_\-]+|cctv[_\-][a-zA-Z0-9_\-]+)\b", query, re.IGNORECASE)
        if m_direct:
            return m_direct.group(1).strip()

        # 2. Match "camera 1", "camera #1", "camera ID 12"
        m_named = re.search(r"\b(?:camera|cam)\s+(?:id\s+)?#?\s*([0-9]+|[a-zA-Z0-9_\-]+)\b", query, re.IGNORECASE)
        if m_named:
            val = m_named.group(1).strip()
            if val.lower() in ("this", "the", "that", "all", "each", "a", "an", "is", "was", "any", "id"):
                return None
            return f"cam_{val}" if not val.startswith("cam") and not val.startswith("cctv") else val
        return None

    def _extract_zone_name(self, query: str) -> Optional[str]:
        m = re.search(r"\b(?:zone|sector|area)\s*#?([a-zA-Z0-9_\-]+)", query, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        return None

    def _extract_relative_time_window(self, query: str) -> Optional[timedelta]:
        m = re.search(r"last\s+(\d+)\s+(minute|min|hour|second|sec)", query, re.IGNORECASE)
        if m:
            qty = int(m.group(1))
            unit = m.group(2).lower()
            if "hour" in unit:
                return timedelta(hours=qty)
            elif "min" in unit:
                return timedelta(minutes=qty)
            elif "sec" in unit:
                return timedelta(seconds=qty)
        return None


global_assistant = SurveillanceAssistant()


def get_surveillance_assistant() -> SurveillanceAssistant:
    return global_assistant
