# Border Intelligence — Implementation Plan

**Problem Statement**: Smart India Hackathon PS SIH26187  
**Status**: Architecture Redesign Phased Implementation Plan  
**Document Owner**: Piyush Chavhan  
**Document Version**: 1.1.0  
**Last Updated**: 2026-08-24  

---

## 1. Plan Baseline & Core Principles

- **Verified Baseline**: **139/139 backend unit tests passing (100%)**; frontend builds cleanly with 0 TypeScript compilation errors.
- **Core Principle**: Structural reorganization and clean domain layering without breaking existing business logic.
- **Mergeability**: Each phase is independently executable, testable, and mergeable.

---

## 2. Phased Execution Roadmap

### Phase 0 — Repository Cleanup (COMPLETE)
- **Status**: `COMPLETED`
- **Actions**:
  1. Deleted orphaned duplicate directory `frontend/src/src/`.
  2. Consolidated all 40 historical sprint markdown documents into the 4 canonical master documents (`BRD.md`, `TECHSTACK.md`, `DESIGN.md`, `IMPLEMENTATION.md`) and archived the historical originals into `docs/archive/`.
- **Exit Criteria**:
  - No duplicate folders.
  - Root directory clean and organized.
  - 139/139 backend tests passing.

---

### Phase 1 — API Gateway & Authentication (COMPLETE)
- **Status**: `COMPLETED`
- **Actions**:
  1. Created `backend/gateway/` module: `auth.py`, `dependencies.py`, `middleware.py`, `rate_limit.py`.
  2. Implemented JWT token issuance, verification (`python-jose`), and password hashing (`passlib[bcrypt]`).
  3. Added `require_role()` dependency for RBAC.
  4. Added query-param token validation for WebSocket endpoint `/api/ws/events`.
  5. Added `DEMO_MODE=true` environment flag for zero-friction judge evaluation walkthroughs.
  6. Added 9 unit tests in `tests/unit/test_gateway_auth.py`.
- **Exit Criteria**:
  - All endpoints require valid JWT authentication unless `DEMO_MODE=true`.
  - 139/139 backend tests pass.

---

### Phase 2 — Shared Kernel Extraction
- **Status**: `PLANNED`
- **Actions**:
  1. Create `backend/shared_kernel/events/`.
  2. Move event bus (`bus.py`), event store (`store.py`), schemas (`schema.py`), snapshots (`snapshots.py`), audit logger (`audit_logger.py`), and SHA-256 hash chaining from `forensics.py` into `backend/shared_kernel/events/`.
  3. Update import paths across dependent modules.
- **Exit Criteria**:
  - Pure refactor with zero logic changes.
  - All 139 backend unit tests pass.

---

### Phase 3 — Domain Service Extraction (Sequential)
- **Status**: `PLANNED`
- **Actions**:
  - Step 3.1: `domains/platform/` — Move `health.py` and `system.py`.
  - Step 3.2: `domains/sensors/` — Move `sensors.py` router and `multi_modal.py`.
  - Step 3.3: `domains/zones/` — Move `zones.py` router, `security_zone.py`, `templates.py`, and `heatmap.py`.
  - Step 3.4: `domains/intelligence/` — Move `intelligence.py`, `threat.py` routers, `assistant.py`, and `threat_engine.py`.
  - Step 3.5: `domains/incidents/` — Move `incidents.py`, `alerts.py`, `export.py`, verification endpoints, `models.py`, `annotations.py`, and `dossier.py`.
  - Step 3.6: `domains/perception/` — Move `cameras.py`, `streaming.py`, and `ingestion/`, `detection/`, `tracking/` directories.
- **Exit Criteria**:
  - `backend/main.py` mounts clean domain routers.
  - All 139 unit tests pass at each step.

---

### Phase 4 — Client Tier Restructure (Frontend Features)
- **Status**: `PLANNED`
- **Actions**:
  1. Reorganize `frontend/src/views/` and `components/` into `frontend/src/features/<feature_name>/`.
  2. Keep shared components in `frontend/src/shared/`.
  3. Apply Vite `manualChunks` configuration to separate Three.js and GSAP into dedicated vendor bundles.
- **Exit Criteria**:
  - `npm run build` succeeds with 0 TypeScript errors.
  - 1.04 MB single-chunk warning resolved.
  - Manual smoke test passes on all 10 views.

---

### Phase 5 — Data Layer Repository Pattern
- **Status**: `PLANNED`
- **Actions**:
  1. Define generic repository interfaces (`IRepository`, `IIncidentRepository`, `ICameraRepository`, `IZoneRepository`).
  2. Implement SQLAlchemy repository classes in domain services.
  3. Refactor direct session queries in domain services to use repository abstractions.
- **Exit Criteria**:
  - Domain services access data strictly via repository interfaces.
  - 139/139 tests pass.

---

### Phase 6 — Edge / Core Split (Design Seam)
- **Status**: `DESIGN ONLY`
- **Actions**:
  1. Document edge/core network boundaries and event serialization contracts.
  2. Package `domains/perception/` for edge deployment (e.g., Jetson Orin) once target hardware is finalized.

---

## 3. Automated Test Coverage Matrix (139/139 Tests)

| Test Module | Test Cases | Domain Area Tested |
|---|---|---|
| `test_gateway_auth.py` | 9 | JWT issuance, password hashing, RBAC, DEMO_MODE fallback, invalid login |
| `test_events.py` | 5 | Event schemas, EventBus pub/sub, Persist-Before-Publish, replay ordering |
| `test_detection.py` | 4 | Model loader, blank frame zero-detection, real object detection, event emission |
| `test_tracking.py` | 9 | Tracker init, single/multi object tracking, track ID persistence, trajectory |
| `test_zones.py` | 4 | Polygon containment, tripwire line crossing, dwell time, transition events |
| `test_zones_api.py` | 2 | Zones CRUD REST API, alert acknowledgement, incidents list |
| `test_loitering.py` | 3 | Loitering dwell thresholds, debouncing, exit/re-entry reset |
| `test_intelligence_assistant.py` | 13 | Grounded NL queries, dwell reasoning, trajectory vectors, anti-hallucination |
| `test_forensics.py` | 2 | SHA-256 deterministic hash computation, verification & audit REST API |
| `test_incident_annotations.py` | 2 | Duty officer notes workflow and REST API |
| `test_incident_dossier.py` | 1 | SitRep tactical dossier compilation and REST API |
| `test_evidence_snapshots.py` | 2 | Incident JPEG snapshot persistence and REST API |
| `test_optical_diagnostics.py` | 5 | Laplacian blur, illumination, glare, blackout detection |
| `test_multi_modal_sensors.py` | 2 | Sensor registry, telemetry ingestion, status REST API |
| `test_threat_engine.py` | 2 | DEFCON levels, composite risk scoring, threat REST API |
| `test_streaming.py` | 3 | WebSocket broadcast, MJPEG video stream, 404 handling |
| `test_websocket_hardening.py` | 2 | Max client limits, slow-client timeout pruning |
| `test_system_metrics_watchdog.py`| 2 | Telemetry endpoints, system status |
| `test_camera_manager.py` | 4 | Camera registration, start/stop streams, frame retrieval |
| `test_camera_reconnect.py` | 3 | Stream retry logic, backoff, reconnection |
| `test_config_profiles.py` | 2 | Profile switcher (Daylight, Night IR, Max FPS) |
| `test_adaptive_stride.py` | 2 | Frame stride adjustment under heavy load |
| `test_exhaustive_verification.py`| 5 | Concurrency stress, DB restart recovery, credential security |
| *Other Unit Modules* | 44 | Hardware detection, heatmap, export, database diagnostics, etc. |
| **TOTAL** | **139** | **100% Pass Rate** |
