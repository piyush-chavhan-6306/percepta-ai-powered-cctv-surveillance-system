# PERCEPTA DEFENSE — MASTER SPECIFICATION & ARCHITECTURE REFERENCE
**Document Version:** 2.0.0 (Production Architecture Freeze)  
**Status:** Canonical Source of Truth  
**Target Audience:** Core Engineers, AI Agents, FreeBuf Frontend Integration Team  

---

## 1. Project Overview
Percepta Defense is an AI-assisted border surveillance intelligence platform designed to transform multi-camera perimeter sensors into actionable, contextual security intelligence. It replaces conventional raw CCTV viewing and alert-flooding motion alarms with an end-to-end perception, tracking, entity resolution, and incident consolidation pipeline.

---

## 2. Product Purpose
Conventional border surveillance systems suffer from catastrophic operator fatigue caused by false positives and alert flooding: 100 consecutive video frames of a subject crossing a perimeter line historically generated 100 independent alerts. Percepta Defense solves this by establishing automated situational awareness:
1. **Background Intelligence**: Background detections and tracks remain internal state without operator interruption.
2. **Deterministic Context**: Ingress, dwell, direction vector, protected zone penetration, and specialized evidence (weapons, plates, faces) are calculated deterministically.
3. **One Incident = One Alert**: All correlated events for a single security breach are consolidated into a persistent Incident. The operator receives exactly one alert, which updates dynamically as threat conditions evolve.
4. **Grounded Inquiries**: Operators can query the system in natural language, receiving strictly database-grounded answers categorized into `[FACT]`, `[INFERENCE]`, and `[UNKNOWN]`.

---

## 3. Core Product Philosophy
- **Detect Everything Useful Internally**: Ingest, detect, and track continuously across all feeds.
- **Track Important Entities Continuously**: Maintain local track continuity, global identity persistence across camera handoffs, and spatial topology transitions.
- **Understand Events Before Alerting**: Differentiate between incidental movement, accidental perimeter clipping, and deliberate deep intrusions.
- **Contextual Threat Scoring**: Detection confidence is **not** threat score. A low-confidence weapon detection or persistent deep entry has a far higher threat score than a high-confidence pedestrian on a public road.
- **Target-Specific Evidence**: If multiple subjects are visible in a frame, only the intruding target subject is extracted and attached to the incident evidence chain. Bystanders are never labeled as evidence.
- **The Dashboard is a View, Not the Engine**: The backend processing pipeline executes continuously regardless of whether an operator has an active browser window open.

---

## 4. System Architecture
The platform is organized into three decoupled, high-performance tiers:
```
┌─────────────────────────────────────────────────────────────────────────┐
│                          PERCEPTA DEFENSE TIER                          │
├─────────────────────────────────────────────────────────────────────────┤
│ 1. EDGE & SENSOR INGESTION LAYER                                        │
│    - RTSP / Video Files / USB Webcams / Simulation / Image Sequences    │
│    - Optical Quality Diagnostics (Laplacian blur, mean luminance)       │
│    - Bounded Async Ring Buffers (Zero Frame Queue Leaks)                │
├─────────────────────────────────────────────────────────────────────────┤
│ 2. PERCEPTION, TRACKING & SPECIALIZED AI                                │
│    - YOLOv8n ONNX Object Detection (80 COCO classes, person, vehicles)  │
│    - ByteTrack MOT (Kalman Filter State Prediction + Hungarian Matching)│
│    - OSNet Deep Re-ID (Appearance Feature Vectors + Topology Gating)    │
│    - Weapon Detector (YOLO gun.pt model)                                │
│    - Face Analytics (YuNet ONNX detector with quality scoring)          │
│    - ANPR Pipeline (Plate Detector + PaddleOCR consensus)               │
├─────────────────────────────────────────────────────────────────────────┤
│ 3. INTELLIGENCE, INCIDENTS & REASONING ENGINE                           │
│    - Global Entity Layer (Persistent ID: GLOBAL-PERSON-042)             │
│    - Camera Topology Service (Directed Graph + Transition Plausibility) │
│    - Zone & Virtual Boundary Engine (Ray-casting, Dwell, Centroid)      │
│    - Event Engine & Frame Debouncer (Suppresses frame-level noise)      │
│    - Deterministic 5-Band Threat Engine (Score 0-100, NORMAL-CRITICAL)  │
│    - Incident Engine (1 Incident = 1 Alert Invariant; Dedup >90%)       │
│    - Grounded Defense AI Assistant ([FACT], [INFERENCE], [UNKNOWN])     │
├─────────────────────────────────────────────────────────────────────────┤
│ 4. STORAGE & PERSISTENCE TIER                                           │
│    - SQLite 3 Write-Ahead Logging (WAL) Mode (`percepta.db`)            │
│    - Normalized Relational Tables with Foreign Key Constraints          │
│    - Local Filesystem Evidence Vault (`storage/evidence/`, `snapshots/`)│
├─────────────────────────────────────────────────────────────────────────┤
│ 5. OPERATOR INTERFACE & TACTICAL PRESENTATION                           │
│    - FastAPI Async REST Gateway + Unified WebSocket Event Bus           │
│    - Tactical Incident Feed (Consolidated Incidents & Status)           │
│    - Multi-Camera Surveillance Wall & Follow-Track Trajectory View      │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 5. End-to-End Intelligence Pipeline
```
[Camera / Sensor Feed]
         │
         ▼
[Ingestion & Optical Diagnostics]
         │
         ▼
[Object Detection (YOLO)]
         │
         ▼
[Local Multi-Object Tracking (ByteTrack)]
         │
         ▼
[Global Entity Resolution (OSNet Re-ID + Topology Gating)]
         │
         ├──> [Specialized AI: Weapon / Face / ANPR]
         │
         ▼
[Zone & Spatial Context (Ray-Casting, Directional Tripwire, Dwell)]
         │
         ▼
[Event Engine & Frame Debouncer]
         │
         ▼
[Deterministic Threat Engine (5-Band Score)]
         │
         ▼
[Target-Specific Evidence Capture (Perpetrators Only)]
         │
         ▼
[Incident Consolidation Engine (DETECTED -> ACTIVE -> ESCALATED -> RESOLVED)]
         │
         ▼
[Alert Deduplication (1 Incident = 1 Operator Alert)]
         │
         ├──> [Tactical Incident Feed (WebSocket Push)]
         └──> [Grounded Defense AI (Operator Query Interface)]
```

---

## 6. Core Concept Definitions

| Concept | Definition | Authoritative DB Representation |
|---|---|---|
| **Detection** | A single raw bounding box, classification label, and model confidence score on a specific video frame. | `detections` |
| **Local Track** | A temporal sequence of detections belonging to one camera feed, maintained by ByteTrack Kalman filtering. | `local_tracks` |
| **Global Entity** | A persistent real-world entity tracked across one or multiple cameras (e.g., `GLOBAL-PERSON-042`). | `global_entities` |
| **Event** | A discrete, meaningful spatial or intelligence state change (e.g., zone entry, tripwire crossing, weapon observed). Frame-level noise is debounced. | `events` |
| **Threat / Risk** | An objective 0–100 score calculated by deterministic rules based on zone sensitivity, dwell time, weapon presence, heading vector, and night conditions. | `threat_assessments` |
| **Incident** | A consolidated security situation grouping all related events, targets, evidence, and threat escalations over time. | `incidents` |
| **Evidence** | Target-specific artifacts (full scene image, target crop, face crop, plate OCR, SHA-256 hash) strictly belonging to the incident's target. | `evidence` |
| **Alert** | The operator-facing dispatch card for an active incident. Under the killer alert rule, **one incident produces exactly one alert**. | `alerts` |
| **AI Query** | An operator request processed by Grounded Defense AI, returning structured facts, inferences, or unknown flags. | `ai_queries` |

---

## 7. Backend Architecture
The backend is built with **Python 3.13**, **FastAPI**, and **SQLAlchemy 2.0 (asyncio)** running on **Uvicorn**:
- `backend/api/`: REST route controllers (`cameras.py`, `entities.py`, `topology.py`, `incidents.py`, `zones.py`, `intelligence.py`, `websocket.py`).
- `backend/detection/`: ONNX and PyTorch model loaders, YOLO detector, YuNet face detector, PaddleOCR ANPR aggregator, and gun detector.
- `backend/tracking/`: ByteTrack wrapper, OSNet Re-ID manager, spatial movement analyzer, and live worker threads.
- `backend/entities/`: Persistent global identity manager, candidate association engine, Follow-Track compiler, and dossier profiling.
- `backend/topology/`: Directed graph camera adjacency, expected transition time intervals, and handoff plausibility gating.
- `backend/zones/`: Vector polygon containment, directional boundary crossing, dwell counters, and spatial heatmaps.
- `backend/events/`: Event debouncer, append-only normalized event store, and forensic SHA-256 tamper auditing.
- `backend/incidents/`: Incident lifecycle coordinator, target-specific evidence validator, timeline builder, and alert deduplicator.
- `backend/intelligence/`: Rule-based deterministic threat engine, multi-modal correlation, and Grounded Defense AI assistant.

---

## 8. Frontend Architecture
The current baseline frontend is built with **React 19.2.8**, **TypeScript ~6.0**, **Vite 8.2**, and **Tailwind CSS 4**:
- `frontend/src/api/client.ts`: Unified typed HTTP client for all backend endpoints.
- `frontend/src/hooks/useWebSocket.ts`: Persistent WebSocket client with exponential backoff reconnect and heartbeats.
- `frontend/src/types/surveillance.ts`: Single-source-of-truth TypeScript definitions matching backend schemas.
- `frontend/src/views/`: Primary operational views (`DashboardView.tsx`, `IncidentsView.tsx`, `ForensicsView.tsx`, `ZonesView.tsx`).
- `frontend/src/components/`: Modular widgets (`AlertPanel.tsx`, `AlertInspector.tsx`, `CameraFeed.tsx`, `ThreatGauge.tsx`, `AIAssistantBar.tsx`).

---

## 9. API Architecture
All endpoints are versioned under `/api`:

### Cameras & Feeds
- `GET /api/cameras`: List all registered cameras, modalities, and operational status.
- `POST /api/cameras`: Register a camera feed (RTSP URL, video file, webcam).
- `DELETE /api/cameras/{id}`: Decommission camera, stop workers, resolve active incidents, and prune topology.
- `POST /api/cameras/{id}/start`: Start live perception worker.
- `POST /api/cameras/{id}/stop`: Stop perception worker.
- `GET /api/cameras/{id}/metrics`: Return live FPS, inference latency, and tracking latency.

### Global Entities & Tracking
- `GET /api/entities`: List global entities with filtering by type, status, and camera.
- `GET /api/entities/{id}`: Core attributes of a single global entity.
- `GET /api/entities/{id}/follow-track`: Ordered multi-camera hops with dwell times and transition confidences.
- `GET /api/entities/{id}/profile`: Complete dossier with observed cameras, local tracks, license plates, and face crops.

### Camera Topology
- `GET /api/topology`: List all registered camera edges, directions, and min/max transition times.
- `POST /api/topology/edges`: Register or update adjacency between two cameras.
- `GET /api/topology/{id}/adjacent`: Query adjacent cameras reachable from a given camera.

### Incidents & Alerts
- `GET /api/incidents`: List consolidated incidents with status and severity filters.
- `GET /api/incidents/{id}/comprehensive-timeline`: Complete chronological timeline answering What, Who, Where, When, How Serious, Why, Evidence, Status, Where Now.
- `POST /api/incidents/{id}/acknowledge`: Acknowledge incident duty review.
- `POST /api/incidents/{id}/resolve`: Resolve incident with operator resolution notes.
- `GET /api/incidents/metrics/deduplication`: Return raw events, incidents, alerts, and suppression rate.
- `GET /api/alerts`: List operator alerts.
- `POST /api/alerts/{id}/acknowledge`: Mark alert acknowledged.

### Zones & Heatmaps
- `GET /api/zones`: List active security zones and virtual boundaries.
- `POST /api/zones`: Create polygonal geofence.
- `POST /api/zones/boundary`: Create directional tripwire boundary.
- `DELETE /api/zones/{id}`: Delete security zone.
- `GET /api/zones/heatmap`: Spatial density coordinates for tactical overlay.

### Intelligence & System
- `POST /api/intelligence/query`: Query Grounded Defense AI.
- `GET /api/threat/level`: Composite sector threat score and DEFCON rating.
- `GET /api/system/audit-logs`: Query administrative audit log entries.
- `GET /api/system/status`: Host telemetry, GPU status, memory, and capture FPS.

---

## 10. WebSocket Architecture
- **Endpoint**: `/ws/events` and `/api/ws/events`
- **Protocol**: JSON text frames over standard WebSocket.
- **Heartbeat**: Bi-directional keepalive ping/pong every 30 seconds.
- **Backpressure & Recovery**: Dropped messages log warnings without blocking background perception workers. Clients re-synchronize state via REST endpoints upon reconnect.
- **Broadcast Payloads**:
  - `INCIDENT_UPDATE`: Incident state transitions, threat escalations.
  - `ALERT_DISPATCH`: New operator alert or alert update.
  - `ZONE_BREACH`: Debounced zone entry/exit events.
  - `CAMERA_STATUS`: Stream online, offline, or degraded status.

---

## 11. Database Schema
Operational SQLite database: `percepta.db` (WAL mode). All tables are fully normalized:

```sql
-- 1. Cameras
CREATE TABLE cameras (
    camera_id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    source_type VARCHAR(32) NOT NULL,
    source_path VARCHAR(512) NOT NULL,
    status VARCHAR(32) NOT NULL,
    location_lat FLOAT,
    location_lon FLOAT,
    zone_metadata JSON,
    connected_cameras JSON,
    expected_direction VARCHAR(32),
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);

-- 2. Camera Sessions
CREATE TABLE sessions (
    session_id VARCHAR(36) PRIMARY KEY,
    camera_id VARCHAR(64) NOT NULL REFERENCES cameras(camera_id),
    started_at DATETIME NOT NULL,
    ended_at DATETIME,
    status VARCHAR(32) NOT NULL,
    fps FLOAT,
    resolution_w INTEGER,
    resolution_h INTEGER
);

-- 3. Local Tracks
CREATE TABLE local_tracks (
    track_pk VARCHAR(36) PRIMARY KEY,
    local_track_id VARCHAR(64) NOT NULL,
    camera_id VARCHAR(64) NOT NULL REFERENCES cameras(camera_id),
    session_id VARCHAR(36) REFERENCES sessions(session_id),
    global_entity_id VARCHAR(36) REFERENCES global_entities(global_entity_id),
    entity_type VARCHAR(32) NOT NULL,
    first_seen DATETIME NOT NULL,
    last_seen DATETIME NOT NULL,
    total_frames INTEGER DEFAULT 1,
    avg_confidence FLOAT,
    status VARCHAR(32) NOT NULL,
    metadata JSON
);

-- 4. Global Entities
CREATE TABLE global_entities (
    global_entity_id VARCHAR(36) PRIMARY KEY,
    display_id VARCHAR(64) UNIQUE NOT NULL,
    entity_type VARCHAR(32) NOT NULL,
    first_seen DATETIME NOT NULL,
    last_seen DATETIME NOT NULL,
    current_camera_id VARCHAR(64),
    current_local_track_id VARCHAR(64),
    status VARCHAR(32) NOT NULL,
    metadata JSON
);

-- 5. Camera Transitions (Cross-Camera Handoffs)
CREATE TABLE camera_transitions (
    transition_id VARCHAR(36) PRIMARY KEY,
    global_entity_id VARCHAR(36) NOT NULL REFERENCES global_entities(global_entity_id),
    from_camera_id VARCHAR(64) NOT NULL,
    from_local_track_id VARCHAR(64) NOT NULL,
    to_camera_id VARCHAR(64) NOT NULL,
    to_local_track_id VARCHAR(64) NOT NULL,
    association_confidence FLOAT NOT NULL,
    transition_time DATETIME NOT NULL,
    association_signals JSON
);

-- 6. Normalized Events
CREATE TABLE events (
    event_id VARCHAR(36) PRIMARY KEY,
    event_type VARCHAR(64) NOT NULL,
    timestamp DATETIME NOT NULL,
    camera_id VARCHAR(64) NOT NULL,
    session_id VARCHAR(36),
    local_track_id VARCHAR(64),
    global_entity_id VARCHAR(36) REFERENCES global_entities(global_entity_id),
    zone_id VARCHAR(36) REFERENCES zones(zone_id),
    incident_id VARCHAR(36) REFERENCES incidents(incident_id),
    entity_type VARCHAR(32),
    confidence FLOAT,
    source VARCHAR(32) NOT NULL DEFAULT 'pipeline',
    metadata JSON,
    evidence_id VARCHAR(36)
);

-- 7. Incidents
CREATE TABLE incidents (
    incident_id VARCHAR(36) PRIMARY KEY,
    incident_type VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL,
    severity VARCHAR(32) NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    resolved_at DATETIME,
    entry_time DATETIME NOT NULL,
    last_seen DATETIME NOT NULL,
    peak_threat FLOAT DEFAULT 0.0,
    current_threat FLOAT DEFAULT 0.0,
    primary_entity_id VARCHAR(36) REFERENCES global_entities(global_entity_id),
    primary_camera_id VARCHAR(64) NOT NULL,
    zone_id VARCHAR(36),
    summary TEXT,
    metadata JSON
);

-- 8. Alerts
CREATE TABLE alerts (
    alert_id VARCHAR(36) PRIMARY KEY,
    incident_id VARCHAR(36) NOT NULL REFERENCES incidents(incident_id),
    operator_severity VARCHAR(32) NOT NULL,
    operator_status VARCHAR(32) NOT NULL,
    acknowledged_at DATETIME,
    acknowledged_by VARCHAR(64),
    message TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);

-- 9. Evidence
CREATE TABLE evidence (
    evidence_id VARCHAR(36) PRIMARY KEY,
    incident_id VARCHAR(36) NOT NULL REFERENCES incidents(incident_id),
    global_entity_id VARCHAR(36) REFERENCES global_entities(global_entity_id),
    camera_id VARCHAR(64) NOT NULL,
    event_id VARCHAR(36) REFERENCES events(event_id),
    timestamp DATETIME NOT NULL,
    evidence_type VARCHAR(32) NOT NULL,
    source_frame_path VARCHAR(512),
    target_crop_path VARCHAR(512),
    target_bbox JSON,
    confidence FLOAT,
    reason TEXT,
    sha256_hash VARCHAR(64),
    metadata JSON
);

-- 10. Security Zones
CREATE TABLE zones (
    zone_id VARCHAR(36) PRIMARY KEY,
    camera_id VARCHAR(64) NOT NULL REFERENCES cameras(camera_id),
    name VARCHAR(128) NOT NULL,
    zone_type VARCHAR(32) NOT NULL,
    polygon JSON NOT NULL,
    severity VARCHAR(32) NOT NULL,
    is_active BOOLEAN DEFAULT 1,
    loitering_threshold_seconds FLOAT,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);

-- 11. Legacy Event Logs (Preserved for non-destructive audit)
CREATE TABLE event_logs (
    seq_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id VARCHAR(36) UNIQUE NOT NULL,
    event_type VARCHAR(32) NOT NULL,
    timestamp DATETIME NOT NULL,
    camera_id VARCHAR(64) NOT NULL,
    track_id VARCHAR(64),
    incident_id VARCHAR(64),
    confidence FLOAT,
    source VARCHAR(32) NOT NULL DEFAULT 'video_file',
    payload TEXT NOT NULL
);
```

---

## 12. Database Relationships
```
cameras (1) ────< (N) sessions
cameras (1) ────< (N) zones
cameras (1) ────< (N) local_tracks
global_entities (1) ────< (N) local_tracks
global_entities (1) ────< (N) camera_transitions
global_entities (1) ────< (N) events
global_entities (1) ────< (N) incidents
incidents (1) ────< (N) events
incidents (1) ────< (1) alerts  (KILLER ALERT INVARIANT)
incidents (1) ────< (N) evidence
```

---

## 13. Camera Lifecycle
- **Registration**: Added via `POST /api/cameras`. Validates stream connection or file existence.
- **Perception Execution**: Explicitly started with `POST /api/cameras/{id}/start`. Instantiates dedicated async worker.
- **Health Monitoring**: Optical diagnostics evaluate blur, glare, and darkness. Disconnections trigger automatic backoff reconnect.
- **Safe Decommission**: Calling `DELETE /api/cameras/{id}`:
  1. Stops running worker thread and releases capture handle.
  2. Resolves all active incidents and operator alerts on that camera (prevents orphaned cards).
  3. Removes camera from topology graph edges.
  4. Removes camera from active registry.

---

## 14. Camera Types
- **Standard Video File**: MP4, MKV, AVI files for deterministic testing and demo replays.
- **RTSP IP Streams**: Network cameras via H.264/H.265 RTSP streams.
- **USB Webcams / V4L2**: Direct hardware capture devices.
- **Thermal & Night IR**: Specialized thermal colorized streams and NIR low-light cameras.
- **Synthetic Simulation**: Programmatic frame generator for load and degradation testing.

---

## 15. Zone Architecture
Zones are defined by normalized 2D polygon vertices $[[x_1, y_1], [x_2, y_2], \dots]$ in image space:
- Containment checked via Ray-Casting Algorithm.
- Zone Severities: `NORMAL`, `SENSITIVE`, `RESTRICTED`, `CRITICAL`.
- Zone Attributes: Loitering threshold (seconds), entry/exit detection, dwell tracking.

---

## 16. Tripwire Architecture
Virtual boundaries configured as directed 2D line segments from Point A to Point B:
- Vector orientation determines directional crossing (`NORTH`, `SOUTH`, `EAST`, `WEST`, `BIDIRECTIONAL`).
- Cross product of motion trajectory vector against boundary line detects boundary crossing.
- Movement opposite to configured breach direction is ignored.

---

## 17. Local Tracking
- **Algorithm**: ByteTrack with two-stage matching (high-confidence detections first, followed by low-confidence recovery).
- **State Estimation**: 8-dimensional Kalman filter estimating $[x, y, a, h, \dot{x}, \dot{y}, \dot{a}, \dot{h}]$.
- **Track Lifecycle**: `Tentative` $\rightarrow$ `Confirmed` $\rightarrow$ `Lost` (max 30 frame buffer) $\rightarrow$ `Terminated`.

---

## 18. Global Entity Tracking
Local tracks across cameras are bound to a persistent Global Entity:
- Identified as `GLOBAL-PERSON-042` or `GLOBAL-VEHICLE-001`.
- Preserves first seen timestamp, last seen timestamp, currently active camera, and current local track ID.
- Resolves candidate identities when confidence is marginal without forcing premature merges.

---

## 19. Cross-Camera Tracking (Re-ID)
Multi-signal association algorithm combines:
1. **Appearance Cosine Similarity**: 512-dimensional feature embedding extracted via OSNet.
2. **Topology Time Plausibility**: Enforces minimum and maximum transition time windows between camera pairs.
3. **Directional Flow**: Handoff direction must align with topology trajectory.
*Rule: Never merge entities solely based on temporal proximity without appearance and topological corroboration.*

---

## 20. Camera Topology
Camera relationships are modeled as an explicit directed graph $G = (V, E)$:
- Vertices $V$: Registered cameras (`CAM-01`, `CAM-02`, etc.).
- Edges $E$: Valid transition corridors between cameras.
- Edge Weights: `min_time_s` (physical travel minimum) and `max_time_s` (maximum window before track is considered lost).
- Plausibility Function: `evaluate_transition_plausibility(from_cam, to_cam, elapsed_seconds)` returns boolean feasibility and penalty factor.

---

## 21. Threat / Risk Model
Threat scoring is strictly **deterministic and rule-based** (zero black-box or non-reproducible scoring). Normalized 0–100 score:
- **0–29 (NORMAL)**: Nominal activity, background movement.
- **30–49 (LOW)**: Minor perimeter boundary clipping, brief entry.
- **50–69 (MEDIUM)**: Prolonged loitering, multiple unauthorized subjects.
- **70–84 (HIGH)**: Deep penetration into restricted zone, movement towards sensitive centroid.
- **85–100 (CRITICAL)**: Intrusion combined with weapon detection or night breach.

Contributing factors are saved as human-readable causal chains (e.g., `["+35 Restricted Zone Intrusion", "+20 Persistent Long-Dwell Presence", "+15 Night Movement"]`).

---

## 22. Alert Deduplication (Killer Alert Invariant)
$$\mathbf{1\text{ Underlying Incident}} = \mathbf{1\text{ Operator Alert}}$$
- When a target enters a restricted zone and remains for 100 frames, exactly **one** alert is emitted.
- Frame 1: Incident detected $\rightarrow$ Alert created $\rightarrow$ Operator notified.
- Frames 2–100: Same target in zone $\rightarrow$ Existing incident threat updates $\rightarrow$ Existing alert updates $\rightarrow$ Zero duplicate alerts created.
- Measured suppression rate: **$90\%$ to $>99\%$ duplicate suppression** across tested scenarios.

---

## 23. Evidence Architecture
Evidence is captured and persisted with cryptographic integrity:
- Full-scene source frame saved to `storage/evidence/`.
- Target crop bounding box extracted and saved.
- SHA-256 hash computed on binary image data and recorded in `evidence.sha256_hash` for chain-of-custody verification.

---

## 24. Target-Specific Evidence
If multiple subjects (e.g., 7 people) are visible in a camera view and only one subject enters a restricted area:
- **Only the intruding target subject** is captured as incident evidence.
- Non-target bystanders are strictly rejected from the incident evidence table (`IncidentManager.attach_target_evidence` validates `target_entity_id == incident.primary_entity_id`).

---

## 25. Incident Timeline
The incident timeline compiles an exhaustive chronological sequence answering:
- **WHAT**: Event classification (`perimeter_breach`, `vehicle_restricted_entry`).
- **WHO**: Associated global entity ID (`GLOBAL-PERSON-042`).
- **WHERE**: Camera ID and zone name.
- **WHEN**: Precise UTC entry time and duration.
- **HOW SERIOUS**: Current threat score and peak threat level.
- **WHY**: Deterministic causal chain of contributing factors.
- **EVIDENCE**: Attached target crop and frame snapshot paths.
- **STATUS**: Incident status (`DETECTED`, `ACTIVE`, `ESCALATED`, `ACKNOWLEDGED`, `RESOLVED`).
- **WHERE NOW**: Current camera and active track location.

---

## 26. Follow Track
Given a global entity ID, the Follow-Track endpoint reconstructs the ordered physical trajectory across cameras:
$$\text{CAM-01 (LOCAL-P17)} \longrightarrow \text{CAM-02 (LOCAL-P04)} \longrightarrow \text{CAM-03 (LOCAL-P12)}$$
Provides entry timestamp, exit timestamp, dwell duration, and transition confidence for each hop.

---

## 27. Person and Vehicle Profiles
- **Person Profile**: Global display ID, first seen, last seen, all cameras visited, all associated local tracks, face observation crops, incident infractions, and peak threat.
- **Vehicle Profile**: Global display ID, vehicle class (truck, car, van), license plate text, OCR confidence, plate crop URI, camera history, and incidents.

---

## 28. ANPR / OCR
- Two-stage pipeline: YOLOv8n-plate detects license plate bounding box $\rightarrow$ PaddleOCR extracts alphanumeric characters.
- Quality filtering: Minimum plate confidence threshold (0.50).
- Consensus: Multi-frame majority voting prevents OCR character hallucination.

---

## 29. Face Processing
- Detector: YuNet ONNX face detector.
- Crop resolution gating: Rejects low-resolution face crops ($<24\times24\text{ px}$).
- Evidence: Saves best quality face crop linked to the person track without claiming biometric identity verification unless authorized watchlists exist.

---

## 30. Weapon Detection
- Model: YOLO gun detection model (`models/weapon/gun.pt`).
- Operational Rule: Reused existing validated weights.
- Escalation: Detection of weapon-like object triggers immediate threat escalation to `CRITICAL` ($\ge 85$).

---

## 31. Drone Capability
- Grounded reality: Aerial/drone video formats and VisDrone datasets are supported in the ingestion pipeline. Dedicated autonomous drone flight control is **not** implemented in this release.

---

## 32. Grounded Defense AI
Operator natural language query layer backed by `SurveillanceAssistant`:
- Standardized Tri-Part Output:
  - `[FACT]`: Direct database records (camera locations, timestamps, plate text).
  - `[INFERENCE]`: Deterministic rule evaluations (boundary crossings, threat level).
  - `[UNKNOWN]`: Explicitly stated when data is missing or indeterminate.
- Guardrails: Strictly refuses to guess or claim human subjective criminal intent.

---

## 33. AI Activity Stream
Provides a low-noise operational activity log summarizing key state events (threat escalations, zone breaches, cross-camera handoffs, incident resolutions) while excluding per-frame raw detection spam.

---

## 34. Continuous Backend Processing
- Ingestion, tracking, threat scoring, and incident maintenance run as independent background asyncio workers.
- The pipeline processes continuous video and logs alerts even when the browser dashboard is closed.
- Operators opening or refreshing the frontend immediately receive current synchronized state.

---

## 35. Authentication
- JWT Bearer token authentication via `/api/auth/token`.
- Current operational mode: `DEMO_MODE=True` allows direct operator evaluation while preserving JWT validation pathways for production deployment.

---

## 36. Dataset Organization
Canonical dataset directory: `dataset/`
```
dataset/
├── surveillance/     (VIRAT, real CCTV feeds, night IR, thermal)
├── perimeter/        (MOT17 perimeter training sequences: MOT17-02 to MOT17-13 FRCNN)
├── drone/            (VisDrone2019 multi-altitude sequences: uav0000086 to 339)
├── face/             (Surveillance face detection benchmarks & LTFT dataset)
├── vehicle/          (Vehicle movement clips & reference manifest)
├── anpr/             (License plate evaluation stream & reference manifest)
├── weapon/           (Weapon detection model reference manifest & gun.pt asset)
└── validation/       (Master Validation Scenario Manifest: Scenarios 1–10)
```

> [!NOTE]
> **Dataset Optimization & MOT17 Test Set Notice**:
> During storage cleanup, unannotated benchmark evaluation sequences (`dataset/perimeter/MOT17/test/`, 3.13 GB) and redundant duplicate image variants (`-DPM`, `-SDP`, 1.70 GB) were pruned following 100% byte-level hash verification. **Full local MOT17 test-set evaluation is no longer available in this repository.** The retained training subset provides verified ground-truth annotations for local tracker regression, but does NOT substitute for the official online evaluation server test set.

---

## 37. Model Organization
Canonical model directory: `models/`
```
models/
├── detection/        (yolov8n.onnx - Primary object detection)
├── face/             (face_detection_yunet_2023mar.onnx)
├── anpr/             (PaddleOCR models + plate detector)
├── reid/             (OSNet appearance embedding model)
└── weapon/           (gun.pt - Weapon detection model)
```

---

## 38. Testing Status
- Automated Test Suite: **233 / 233 tests passing (100%)**
  - Unit tests (`tests/unit/`): 216 tests
  - Integration tests (`tests/integration/`): 1 test
  - Failure/Fault isolation tests (`tests/failure/`): 16 tests
- Master Verification Suites:
  - `test_phase6_to_8.py`: Global entity and topology handoffs.
  - `test_phases_9_to_16.py`: Zones, threat engine, killer alert deduplication, target evidence.
  - `test_phase_31_to_35_master_scenarios.py`: Master scenarios 1–10 and multi-camera killer alert test.
  - `test_camera_lifecycle.py`: Safe decommission and orphan cleanup.
  - `test_grounded_defense_ai.py`: Factual grounding and intent refusal.

---

## 39. Deployment Architecture
- **Runtime**: Python 3.13 virtual environment (`./venv`).
- **ASGI Process**: `uvicorn backend.main:app --host 0.0.0.0 --port 8000`.
- **Frontend Distribution**: Static production build generated via `npm run build` into `frontend/dist/`. Served via Nginx or FastAPI static mount.
- **Database**: Single-file SQLite WAL database (`percepta.db`). Zero external database service dependency for standalone tactical edge deployment.

---

## 40. Known Limitations
1. **CPU Inference Latency**: When CUDA hardware is unavailable, ONNX CPU inference operates between 15–30 FPS depending on host CPU cores.
2. **Re-ID Resolution Threshold**: OSNet appearance vectors require bounding boxes $>64\times128\text{ px}$. Highly distant targets rely on spatial-temporal topology gating.
3. **Plate Contrast**: ANPR accuracy degrades in extreme glare or darkness without infrared illumination; returns `UNKNOWN` rather than guessing characters.

---

## 41. Performance Limitations
- Tested baseline throughput: Up to 4 concurrent simulated camera streams at 30 FPS on multi-core workstation.
- Peak RAM usage: $\sim1.2\text{ GB}$ with models resident in memory.
- Bounded memory buffers: Fixed queue sizes ensure zero memory leaks over long runs.

---

## 42. Security Notes
- Input validation enforced via Pydantic on all REST endpoints.
- SQL injection prevention: All database operations use SQLAlchemy parameterized queries.
- Forensic integrity: Critical events and evidence record SHA-256 hashes for non-repudiation.
- Zero secrets committed: `.env` excluded from version control via `.gitignore`.

---

## 43. Feature Classification Matrix

| Feature | Classification | Description |
|---|---|---|
| YOLO Object Detection | **IMPLEMENTED** | Multi-class detection (person, vehicle) |
| ByteTrack MOT | **IMPLEMENTED** | Kalman filter tracking |
| Global Entity Resolution | **IMPLEMENTED** | Persistent multi-camera identity |
| OSNet Re-ID | **IMPLEMENTED** | Deep appearance cosine matching |
| Camera Topology | **IMPLEMENTED** | Graph-based transition plausibility |
| Zone & Tripwire Monitoring | **IMPLEMENTED** | Ray-casting polygon & directional boundaries |
| Deterministic Threat Engine | **IMPLEMENTED** | 5-band score with causal chains |
| Alert Deduplication | **IMPLEMENTED** | 1 incident = 1 alert invariant |
| Target-Specific Evidence | **IMPLEMENTED** | Rejects non-target bystander evidence |
| Follow Track & Timeline | **IMPLEMENTED** | Multi-camera trajectory reconstruction |
| Grounded Defense AI | **IMPLEMENTED** | Anti-hallucination structured query layer |
| Weapon Detection | **IMPLEMENTED** | YOLO gun model integration |
| ANPR / OCR | **IMPLEMENTED** | License plate extraction & consensus |
| Face Analytics | **IMPLEMENTED** | YuNet surveillance face detection |
| Autonomous Drone Flight | **NOT IMPLEMENTED** | Drone video ingestion supported; flight control is out of scope |
| Cloud Multi-Region Cluster | **PLANNED** | Multi-node deployment with Redis pub/sub broker |

---

## 44. Frontend UI Architecture
- Navigation Views:
  1. **Dashboard**: Tactical multi-camera wall, threat gauge, live alert feed.
  2. **Incidents**: Chronological incident feed, detailed timeline, dossier inspection.
  3. **Zones**: Polygon and boundary drawing editor with spatial density heatmap.
  4. **Forensics**: Event audit log, hash verification, tamper detection.
  5. **Intelligence**: Grounded AI assistant conversation panel.

---

## 45. Important Backend Contracts for Frontend Developers
Frontend engineers must adhere to these frozen contracts:
1. **Camera IDs**: String format (`CAM-01`, `CAM-02`).
2. **Global Entity IDs**: UUID or display format (`GLOBAL-PERSON-042`).
3. **Alert Severity**: Strings (`NORMAL`, `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
4. **Incident Lifecycle Statuses**: `DETECTED`, `ACTIVE`, `ESCALATED`, `ACKNOWLEDGED`, `RESOLVED`.
5. **WebSocket Message Envelope**:
   ```json
   {
     "event_type": "INCIDENT_UPDATE",
     "incident_id": "...",
     "camera_id": "CAM-01",
     "severity": "HIGH",
     "threat_score": 78.0,
     "message": "...",
     "timestamp": "2026-09-11T12:00:00Z"
   }
   ```

---

## 46. FreeBuf Integration Rules

> [!IMPORTANT]
> ### Rules for FreeBuf UI Redesign
> **FreeBuf may freely redesign:**
> - Visual design tokens, typography, dark themes, and styling.
> - Layout grids, camera wall arrangements, and responsiveness.
> - Component cards, modal dialogs, and slide-over drawers.
> - Three.js 3D spatial terrain and camera frustum visualizations.
> - GSAP animations, transitions, and micro-interactions.
> 
> **FreeBuf MUST NOT modify:**
> - Backend REST endpoints and URL paths.
> - WebSocket protocol and message payload schemas.
> - Database models or column semantics.
> - The **ONE INCIDENT = ONE OPERATOR ALERT** backend invariant.
> - Threat score calculations (the frontend displays threat; it does not calculate it).
> - Target evidence scoping (the frontend displays target crops; it does not assign guilt).

---

## 47. Development Workflow
$$\mathbf{PLAN} \longrightarrow \mathbf{IMPLEMENT} \longrightarrow \mathbf{TEST} \longrightarrow \mathbf{DEBUG} \longrightarrow \mathbf{REVIEW} \longrightarrow \mathbf{COMMIT}$$
1. Verify working test baseline (`pytest tests/ -q`).
2. Implement scoped changes without breaking backend contracts.
3. Validate backend tests and frontend build (`npm run build`).
4. Update `PERCEPTA_EXECUTION_CHECKPOINT.md`.

---

## 48. Clean Repository Structure
```
d:/SIH   border cctv/
├── backend/                  # FastAPI backend application
│   ├── api/                  # REST controllers & WebSocket routes
│   ├── database/             # SQLAlchemy models & session factory
│   ├── detection/            # YOLO, YuNet, ANPR, Weapon detectors
│   ├── entities/             # Global entity management & Follow-Track
│   ├── events/               # Event debouncer, store, forensics
│   ├── gateway/              # Authentication & rate limiting
│   ├── incidents/            # Incident lifecycle & alert deduplicator
│   ├── ingestion/            # Camera stream adapters & manager
│   ├── intelligence/         # Threat engine & Grounded Defense AI
│   ├── topology/             # Camera adjacency & transition plausibility
│   ├── tracking/             # ByteTrack & OSNet Re-ID
│   └── zones/                # Geofence & boundary monitoring
├── frontend/                 # React 19 + TypeScript + Vite UI
│   ├── src/
│   │   ├── api/              # Typed REST client
│   │   ├── components/       # UI components & widgets
│   │   ├── hooks/            # WebSocket & UI hooks
│   │   ├── types/            # Single-source-of-truth TypeScript types
│   │   └── views/            # Operational dashboard views
│   └── package.json
├── dataset/                  # Canonical surveillance datasets
├── models/                   # Canonical neural network model weights
├── storage/                  # Persisted evidence, snapshots, zones config
├── tests/                    # 233 automated test suites
│   ├── unit/                 # Unit tests
│   ├── integration/          # Tracking pipeline integration tests
│   └── failure/              # Fault tolerance & degradation tests
├── docs/                     # Project documentation
│   └── archive/              # 40 historical planning and audit reports
├── scripts/                  # Utility and diagnostic scripts
├── percepta.db               # Operational SQLite WAL database
├── PERCEPTA_MASTER.md        # Single authoritative source of truth
├── README.md                 # Concise quick-start guide
└── requirements.txt          # Python runtime dependencies
```

---

## 49. Cleanup History
During the repository consolidation pass:
1. **Documentation Consolidation**: Consolidated multiple fragmented planning and status markdown files into this authoritative master specification (`PERCEPTA_MASTER.md`). 40 historical audit and planning documents preserved safely in `docs/archive/`.
2. **Database Hardening**: Verified 18 physical SQLite tables in `percepta.db`. Populated missing camera foreign key references for `CAM-01` and `TEST-CAM-01`, reducing FK violations to **0** across all 144,603 rows. Verified 1:1 legacy migration (36,432 rows in `event_logs` $\equiv$ 36,432 rows in `events`).
3. **Artifact Cleanup**: Safely deleted temporary 641 MB scratch video file (`scratch/test_virat.mkv`). Cleaned all Python `__pycache__` and `.pytest_cache` bytecodes. Added `scratch/` to `.gitignore`.
4. **Frontend Build Verification**: Resolved TypeScript compiler options, installed missing component peer dependencies, and verified `npm run build` compiles cleanly in $\sim650\text{ ms}$.

---

## 50. Current Project Status
- **Backend Intelligence Architecture**: **FROZEN & VERIFIED** (233 / 233 tests passing).
- **Database Integrity**: **PRISTINE** (0 FK violations, WAL mode active).
- **Frontend Build**: **COMPLIANT & PASSING** (Ready for FreeBuf UI redesign).
- **Handoff Readiness**: **APPROVED FOR FREEBUF REDESIGN**.
