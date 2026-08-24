# BORDER INTELLIGENCE — COMPLETE API KNOWLEDGE BASE

**Project**: Border Intelligence (PS SIH26187)  
**Total Endpoints**: 47 Endpoints across 13 FastAPI Routers  
**Base URL**: `http://127.0.0.1:8000`  
**WebSocket URL**: `ws://127.0.0.1:8000/ws/events`  
**API Documentation**: `http://127.0.0.1:8000/docs` (Swagger UI) & `/redoc`  

---

## 1. System & Health Router (`backend/api/health.py`, `backend/api/system.py`)

### `GET /api/health`
- **Router**: `health_router`
- **Request Model**: None
- **Response Model**: `{"status": "healthy", "service": str, "timestamp": str, "database": "connected", "mode": str}`
- **Dependencies**: Database Engine
- **Database Access**: Read (PRAGMA ping)
- **Events Generated**: None
- **Security Validation**: None
- **Error Cases**: 500 if database unreachable
- **Covering Tests**: `tests/unit/test_events.py::test_fastapi_health_and_replay_endpoints`
- **Downstream Consumers**: Uptime monitors, Docker healthcheck, Frontend header

### `GET /api/readiness`
- **Router**: `health_router`
- **Request Model**: None
- **Response Model**: `{"status": "ready"|"not_ready", "checks": {"database": bool, "detector_loaded": bool, "event_bus": bool, "storage": bool}}`
- **Dependencies**: Model Loader, EventStore, EventBus
- **Database Access**: Read
- **Events Generated**: None
- **Security Validation**: None
- **Error Cases**: 503 if any critical subsystem is unprimed
- **Covering Tests**: `tests/unit/test_api_cameras_alerts_system.py::test_api_readiness_probe_and_demo_reset`
- **Downstream Consumers**: Kubernetes readiness probes, system monitoring dashboards

### `GET /api/system/status`
- **Router**: `system_router`
- **Request Model**: None
- **Response Model**: System uptime, active camera count, dropped frames, memory usage
- **Dependencies**: System watchdog, CameraManager
- **Database Access**: None (In-memory telemetry)
- **Events Generated**: None
- **Covering Tests**: `tests/unit/test_system_metrics_watchdog.py::test_system_status_endpoint_telemetry`

### `GET /api/system/metrics`
- **Router**: `system_router`
- **Request Model**: None
- **Response Model**: `SystemMetrics` (Capture FPS, AI Processing FPS, inference latency ms, tracking latency ms, frame stride, memory MB)
- **Dependencies**: TrackingPipeline watchdog
- **Database Access**: None
- **Events Generated**: None
- **Covering Tests**: `tests/unit/test_system_metrics_watchdog.py::test_system_metrics_watchdog_endpoint`
- **Downstream Consumers**: Frontend Telemetry HUD

### `GET /api/system/coverage-report`
- **Router**: `system_router`
- **Request Model**: None
- **Response Model**: `CoverageReport` (Fleet coverage percentage, Readiness grade: `GRADE_A_COMBAT_READY` | `GRADE_B_DEGRADED` | `GRADE_C_VULNERABLE`, Strategic assessment)
- **Dependencies**: CameraManager, EventStore
- **Database Access**: Read
- **Covering Tests**: `tests/unit/test_coverage_analytics.py::test_coverage_report_rest_api`
- **Downstream Consumers**: Command Post overview

### `GET /api/system/profiles`
- **Router**: `system_router`
- **Request Model**: None
- **Response Model**: `{"active_profile": OperationalProfile, "available_profiles": List[OperationalProfile]}`
- **Covering Tests**: `tests/unit/test_config_profiles.py::test_operational_profiles_rest_api`

### `POST /api/system/profiles/apply`
- **Router**: `system_router`
- **Request Model**: `{"profile_id": "STANDARD_DAY" | "HIGH_SENSITIVITY_NIGHT" | "ADVERSE_WEATHER_STORM" | "HIGH_TRAFFIC_CONVOY"}`
- **Response Model**: `{"status": "applied", "active_profile": OperationalProfile}`
- **Covering Tests**: `tests/unit/test_config_profiles.py::test_operational_profiles_switching`

### `GET /api/system/audit-logs`
- **Router**: `system_router`
- **Request Model**: Query: `limit: int = 100`
- **Response Model**: `{"count": int, "audit_logs": List[AuditLogEntry]}`
- **Database Access**: Read from `audit_logs` table
- **Covering Tests**: `tests/unit/test_audit_logger.py::test_audit_logs_rest_api`

### `GET /api/system/db-diagnostics`
- **Router**: `system_router`
- **Request Model**: None
- **Response Model**: `DatabaseDiagnostics` (Journal mode, SQLite storage MB, WAL size MB, PostgreSQL migration readiness)
- **Covering Tests**: `tests/unit/test_database_diagnostics.py::test_database_diagnostics_rest_api`

### `POST /api/system/demo-reset`
- **Router**: `system_router`
- **Request Model**: None
- **Response Model**: `{"status": "reset_complete", "timestamp": str, "active_cameras": int}`
- **Covering Tests**: `tests/unit/test_api_cameras_alerts_system.py::test_api_readiness_probe_and_demo_reset`
- **Downstream Consumers**: Judge demonstration UI

---

## 2. Cameras Router (`backend/api/cameras.py`)

### `GET /api/cameras`
- **Request Model**: None
- **Response Model**: `{"count": int, "cameras": List[CameraRecord]}`
- **Covering Tests**: `tests/unit/test_api_cameras_alerts_system.py::test_api_cameras_endpoints`

### `POST /api/cameras/register`
- **Request Model**: `{"camera_id": str, "name": str, "source_type": str, "source_url": Optional[str], "location_label": str, "fps": int}`
- **Response Model**: `CameraRecord` (Masked credentials)
- **Security Validation**: RTSP credential masking, directory sanitization
- **Covering Tests**: `tests/unit/test_api_cameras_alerts_system.py::test_api_cameras_register_deregister_reconnect`

### `GET /api/cameras/{camera_id}`
- **Response Model**: `CameraRecord` (404 if unknown)
- **Covering Tests**: `tests/unit/test_camera_manager.py`

### `POST /api/cameras/{camera_id}/start` & `POST /api/cameras/{camera_id}/stop`
- **Response Model**: `{"camera_id": str, "status": "started" | "stopped"}`
- **Covering Tests**: `tests/unit/test_api_cameras_alerts_system.py::test_api_cameras_endpoints`

### `POST /api/cameras/{camera_id}/reconnect`
- **Response Model**: `{"camera_id": str, "status": "reconnected"}`
- **Covering Tests**: `tests/unit/test_camera_reconnect.py::test_camera_reconnect_success_after_retry`

### `DELETE /api/cameras/{camera_id}`
- **Response Model**: `{"camera_id": str, "status": "deleted"}`
- **Covering Tests**: `tests/unit/test_api_cameras_alerts_system.py::test_api_cameras_register_deregister_reconnect`

### `GET /api/cameras/{camera_id}/diagnostics`
- **Response Model**: `CameraDiagnostics` (Blur score, mean brightness, glare percentage, darkness ratio, status: `OPTIMAL` | `OCCLUDED_OR_BLURRED` | `BLINDED_GLARE` | `LOW_LIGHT_DEGRADED`)
- **Covering Tests**: `tests/unit/test_optical_diagnostics.py::test_camera_diagnostics_rest_api`

### `GET /api/cameras/{camera_id}/heatmap`
- **Response Model**: `HeatmapResponse` (16x16 density matrix, total points, hotspots identified)
- **Covering Tests**: `tests/unit/test_heatmap.py::test_spatial_heatmap_rest_api`

---

## 3. Alerts & Incidents Router (`backend/api/alerts.py`, `backend/api/incidents.py`)

### `GET /api/alerts`
- **Query Params**: `camera_id: Optional[str]`, `severity: Optional[str]`, `limit: int = 50`
- **Response Model**: `{"count": int, "alerts": List[AlertItem]}`
- **Database Access**: Read from `event_logs` where `event_type = 'ALERT'`
- **Covering Tests**: `tests/unit/test_api_cameras_alerts_system.py::test_api_alerts_and_incidents_endpoints`

### `POST /api/alerts/{event_id}/ack` (or `/acknowledge`)
- **Response Model**: `{"event_id": str, "status": "acknowledged"}`
- **Database Access**: Update `event_logs.is_acknowledged = 1`
- **Covering Tests**: `tests/unit/test_zones_api.py::test_alert_acknowledgement_and_incidents_list_api`

### `GET /api/incidents`
- **Query Params**: `camera_id: Optional[str]`, `limit: int = 50`
- **Response Model**: `{"count": int, "incidents": List[IncidentSummary]}`
- **Covering Tests**: `tests/unit/test_zones_api.py::test_alert_acknowledgement_and_incidents_list_api`

### `GET /api/incidents/{incident_id}` & `GET /api/incidents/{incident_id}/timeline`
- **Response Model**: `{"incident_id": str, "camera_id": str, "count": int, "timeline": List[TimelineEvent]}`
- **Covering Tests**: `tests/unit/test_incident_dossier.py`

### `GET /api/incidents/{incident_id}/dossier`
- **Response Model**: `IncidentDossier` (Duration, motion summary, infractions, forensic SHA-256 token, tactical SitRep)
- **Covering Tests**: `tests/unit/test_incident_dossier.py::test_incident_dossier_compilation_and_rest_api`

### `GET /api/incidents/{incident_id}/notes`
- **Response Model**: `{"incident_id": str, "count": int, "annotations": List[OperatorAnnotation]}`
- **Covering Tests**: `tests/unit/test_incident_annotations.py::test_operator_annotations_rest_api`

### `POST /api/incidents/{incident_id}/notes`
- **Request Model**: `{"operator_callsign": str, "note": str, "disposition": str}`
- **Response Model**: `OperatorAnnotation`
- **Database Access**: Write to `incident_annotations` table
- **Covering Tests**: `tests/unit/test_incident_annotations.py::test_operator_annotations_workflow`

---

## 4. Security Zones Router (`backend/api/zones.py`)

### `GET /api/zones`
- **Response Model**: `{"zones": List[SecurityZone], "boundaries": List[VirtualBoundary]}`
- **Covering Tests**: `tests/unit/test_zones_api.py::test_zones_and_boundaries_crud_api`

### `POST /api/zones`
- **Request Model**: `{"zone_id": str, "name": str, "polygon": List[List[float]], "severity": str, "loitering_threshold_seconds": Optional[float]}`
- **Response Model**: Created zone object
- **Covering Tests**: `tests/unit/test_zones_api.py::test_zones_and_boundaries_crud_api`

### `POST /api/zones/boundary`
- **Request Model**: `{"boundary_id": str, "name": str, "pt1": [float, float], "pt2": [float, float], "severity": str}`
- **Response Model**: Created boundary object
- **Covering Tests**: `tests/unit/test_zones_api.py::test_zones_and_boundaries_crud_api`

### `DELETE /api/zones/{zone_id}`
- **Response Model**: `{"zone_id": str, "status": "deleted"}`
- **Covering Tests**: `tests/unit/test_zones_api.py::test_zones_and_boundaries_crud_api`

### `GET /api/zones/templates`
- **Response Model**: `{"templates": List[ZoneTemplate]}`
- **Covering Tests**: `tests/unit/test_zone_templates.py::test_zone_templates_rest_api`

### `POST /api/zones/apply-template`
- **Request Model**: `{"template_id": str, "zone_id_suffix": str, "custom_name": Optional[str]}`
- **Response Model**: Applied template zone/boundary
- **Covering Tests**: `tests/unit/test_zone_templates.py::test_list_and_apply_tactical_templates`

---

## 5. Grounded Intelligence Router (`backend/api/intelligence.py`)

### `POST /api/intelligence/query`
- **Request Model**: `{"query": str, "camera_id": Optional[str], "start_time": Optional[datetime], "end_time": Optional[datetime]}`
- **Response Model**:
  - `status`: `"answered"` | `"refused"` | `"no_records_found"` | `"invalid_query"`
  - `observed_facts`: `List[str]` (Immutable SQLite WAL evidence)
  - `rule_results`: `List[str]` (Deterministic threshold logic)
  - `interpretation`: `str` (Strictly derived summary)
  - `evidence`: `List[Dict[str, Any]]`
  - `grounding_status`: `"grounded"` | `"refusal"` | `"no_data"`
- **Security Validation**: Biometric refusal, weapon refusal, intent speculation refusal, cross-camera identity refusal, SQL injection refusal
- **Covering Tests**: `tests/unit/test_intelligence_assistant.py` (14 tests)

---

## 6. Threat & Forensics Router (`backend/api/threat.py`, `backend/api/forensics.py`, `backend/api/export.py`)

### `GET /api/threat/level`
- **Query Params**: `camera_id: Optional[str]`
- **Response Model**: `ThreatAssessment` (Threat level: `DEFCON_GREEN` | `DEFCON_YELLOW` | `DEFCON_ORANGE` | `DEFCON_RED`, Threat score: 0-100, Active breaches, Active loiterers, Contributing factors, Recommended action)
- **Covering Tests**: `tests/unit/test_threat_engine.py::test_threat_level_rest_api`

### `GET /api/evidence/verify/{event_id}`
- **Response Model**: `ForensicVerificationResult` (Computed SHA-256 hash, tamper status: `VERIFIED_AUTHENTIC` | `CORRUPTED_OR_TAMPERED`, is_authentic: bool)
- **Covering Tests**: `tests/unit/test_forensics.py::test_forensics_rest_api_verify_and_audit`

### `GET /api/evidence/audit-integrity`
- **Query Params**: `limit: int = 200`
- **Response Model**: `IntegrityAuditReport` (Total checked, authentic count, tampered count, root chain hash, audit verdict)
- **Covering Tests**: `tests/unit/test_forensics.py::test_forensics_rest_api_verify_and_audit`

### `GET /api/evidence/snapshots/{incident_id}`
- **Response Model**: `{"incident_id": str, "count": int, "snapshots": List[SnapshotMetadata]}`
- **Covering Tests**: `tests/unit/test_evidence_snapshots.py::test_evidence_snapshots_rest_api`

### `GET /api/evidence/snapshots/file/{filename}`
- **Response Model**: Binary JPEG image file (`image/jpeg`)
- **Security Validation**: Directory traversal prevention
- **Covering Tests**: `tests/unit/test_evidence_snapshots.py::test_save_and_list_incident_snapshots`

### `GET /api/events/export`
- **Query Params**: `format: "json" | "csv"`, `camera_id: Optional[str]`, `event_type: Optional[str]`
- **Response Model**: File download (`text/csv` or `application/json`)
- **Covering Tests**: `tests/unit/test_event_export.py::test_event_export_json_and_csv_rest_api`

---

## 7. Multi-Modal Sensors Router (`backend/api/sensors.py`)

### `GET /api/sensors/status`
- **Response Model**: `{"total_sensors": int, "sensors": Dict[str, SensorChannelInfo]}`
- **Covering Tests**: `tests/unit/test_multi_modal_sensors.py::test_sensor_ingest_and_status_rest_api`

### `POST /api/sensors/ingest`
- **Request Model**: `{"sensor_id": str, "sensor_type": "RADAR"|"SEISMIC"|"THERMAL_IR"|"RF_DETECTOR", "sector_id": str, "confidence": float, "data": Dict[str, Any]}`
- **Response Model**: `{"status": "ingested", "event_id": str}`
- **Covering Tests**: `tests/unit/test_multi_modal_sensors.py::test_sensor_ingest_and_status_rest_api`

---

## 8. Video & WebSocket Streaming Router (`backend/api/streaming.py`)

### `GET /api/stream/video/{camera_id}`
- **Response Model**: `multipart/x-mixed-replace; boundary=frame` (MJPEG video stream with telemetry overlay)
- **Covering Tests**: `tests/unit/test_streaming.py::test_mjpeg_video_stream_endpoint`

### `GET /api/stream/raw/{camera_id}`
- **Response Model**: Clean MJPEG raw stream without bounding box overlays
- **Covering Tests**: `tests/unit/test_streaming.py`

### `WebSocket /ws/events`
- **Protocol**: JSON WebSocket Event Stream
- **Keepalive**: Ping/Pong every 25s
- **Payload Types**: `alert`, `zone`, `tracking`, `detection`, `incident`, `system`, `pong`
- **Security & Resilience**: Client connection limits (max 50 concurrent), slow client pruning (timeout: 1.0s), subscriber isolation
- **Covering Tests**: `tests/unit/test_streaming.py::test_websocket_events_endpoint_and_broadcast`, `tests/unit/test_websocket_hardening.py`
