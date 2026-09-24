# PERCEPTA DEFENSE — ARCHITECTURE ASSESSMENT
## Phase 0: Complete Repository Inspection

**Date:** September 10, 2026
**Repository:** D:\SIH   border cctv
**Total Size:** ~13.3 GB (excl. caches), 46,449 files, 374 directories

---

## 1. CURRENT ARCHITECTURE

### 1.1 Tech Stack
| Layer | Technology |
|-------|-----------|
| Backend | FastAPI + SQLAlchemy 2.0 (async, SQLite WAL) + aiosqlite |
| Frontend | React 19 + TypeScript 6 + Vite 8 + Tailwind 4 + Radix UI |
| Detection | YOLOv8n (ONNX Runtime) + YuNet face (ONNX) + PP-OCRv3 |
| Tracking | ByteTrack (custom wrapper) + OSNet Re-ID (ONNX) |
| Communication | REST API + WebSocket (auto-reconnect) |
| Auth | JWT (DEMO_MODE bypass, hardcoded admin@123) |

### 1.2 Logical Pipeline (As-Is)
```
Camera/Video → Ingestion → YOLO Detection → ByteTrack → Zone Check → EventStore → EventBus → WebSocket → Dashboard
                                                                        ↓
                                                                  Evidence Detectors (YuNet/Plate/OCR)
                                                                        ↓
                                                                  Threat Engine (rule-based)
                                                                        ↓
                                                                  Alert API → AlertPanel
```

### 1.3 Backend Structure (72 Python files, 10 subpackages)
- **api/** — 13 routers (alerts, cameras, events, export, forensics, health, incidents, intelligence, sensors, streaming, system, threat, zones)
- **detection/** — 10 modules (detector, onnx_detector, model_loader, anpr, plate_aggregator, face_analytics, evidence_detectors, thermal_processor, tamper)
- **tracking/** — 7 modules (pipeline, tracker, bytetrack_wrapper, reid_manager, movement, overlay, live_worker)
- **events/** — 6 modules (bus, store, schema, snapshots, forensics, audit_logger)
- **ingestion/** — 10 modules (adapter, rtsp_adapter, video_adapter, webcam_adapter, simulation_adapter, image_sequence_adapter, sensor_adapter, camera_manager, frame_buffer, optical_diagnostics)
- **zones/** — 4 modules (security_zone, heatmap, templates)
- **intelligence/** — 4 modules (assistant, correlation, threat_engine, query_parsing)
- **incidents/** — 3 modules (models, dossier, annotations)
- **gateway/** — 4 modules (auth, middleware, dependencies, rate_limit)
- **sensors/** — 1 module (multi_modal)

### 1.4 Frontend Structure (88 source files)
- **pages/** — 4 pages (Landing, Auth, Dashboard, NotFound)
- **components/** — 14 custom + 66 shadcn/ui
- **hooks/** — 4 hooks (useWebSocket, useDisplayedImageRect, use-mobile, use-auth)
- **api/** — 1 REST client (394 lines)
- **types/** — 1 surveillance types file (304 lines)

---

## 2. REUSABLE / WORKING COMPONENTS

| Component | Status | Notes |
|-----------|--------|-------|
| **YOLOv8n detection** | ✅ Working | 80-class COCO, ONNX, ~95ms/frame at 1080p |
| **ByteTrack tracking** | ✅ Working | Custom wrapper with spatial dedup, ~5ms/frame |
| **YuNet face detection** | ✅ Working | Crop-based, threshold 0.3, detects surveillance faces |
| **Plate detection + OCR** | ✅ Working | YOLOv8n-plate + PP-OCRv3, multi-frame consensus |
| **OSNet Re-ID** | ⚠️ Partial | Model loaded, embeddings computed, but no global entity management |
| **Zone monitoring** | ✅ Working | Polygon containment, tripwire, templates |
| **Event bus** | ✅ Working | Async pub/sub, persist-before-publish |
| **Threat engine** | ✅ Working | Deterministic rule-based scoring with factor explanations |
| **Intelligence assistant** | ✅ Working | Anti-hallucination NL query, structured DB retrieval |
| **Camera adapters** | ✅ Working | RTSP, USB, file, simulation, image sequence |
| **Evidence capture** | ✅ Working | JPEG + SHA-256 chain-of-custody |
| **Frontend dashboard** | ✅ Working | Real-time alerts, camera feeds, threat gauge, AI assistant |
| **WebSocket streaming** | ✅ Working | Auto-reconnect, keepalive, event broadcasting |
| **51 unit tests** | ✅ Existing | Good coverage across major modules |

---

## 3. ARCHITECTURAL PROBLEMS

### 3.1 Critical: Single-Table Database
- **ALL data** (detections, tracking, alerts, incidents, ANPR, face, correlation) stored in ONE `event_logs` table as JSON blobs
- No relational integrity between incidents and constituent events
- No dedicated tables for cameras, zones, incidents, entities, evidence
- Querying specific fields requires JSON parsing of the `payload` column
- `global_person_id` exists only in Pydantic schema, not as a DB column

### 3.2 Critical: No Persistence for Core Entities
- **Cameras** — in-memory only (CameraManager), lost on restart
- **Zones** — in-memory only (SecurityZoneMonitor), lost on restart
- **Incidents** — computed on-the-fly by grouping event `incident_id` values
- **Global entities** — Re-ID computes embeddings but no persistent entity table
- **Alerts** — derived from events, no separate alert state management

### 3.3 Critical: No Incident Engine
- Incidents are ephemeral groupings of events
- No incident lifecycle (DETECTED → EVALUATING → ACTIVE → RESOLVED)
- No incident deduplication — each zone event can create a new alert
- No cooldown/debounce at the incident level
- Frontend receives raw detection-level alerts, not incident-level

### 3.4 High: Alert Spam
- Every zone event creates a separate alert
- No tracking-aware grouping
- No per-frame deduplication
- Operator sees dozens of alerts for one physical event

### 3.5 High: No Cross-Camera Global Entity Management
- Re-ID manager computes appearance embeddings
- No global entity table with camera transitions
- No camera topology modeling
- No entity profiles (person/vehicle history)

### 3.6 Medium: Frontend Oversized Components
- `Landing.tsx` — 949 lines (8 inline chapter components)
- `CameraFeed.tsx` — 770 lines (viewport + zone drawing + replay + modality)
- `AddCameraModal.tsx` — 591 lines (upload + RTSP + webcam tabs)
- `AlertInspector.tsx` — 491 lines (evidence + chain + telemetry)
- `Dashboard.tsx` — 515 lines (orchestrator + inline components)

### 3.7 Medium: Duplicate WebSocket Connections
- `Dashboard.tsx` and `AlertPanel.tsx` each open independent WebSocket connections
- Should be a single connection with shared event dispatcher

### 3.8 Medium: Dead Code
- `TiltCard.tsx` — superseded by PremiumCard, unused
- `MagneticButton.tsx` — unused
- `LogoDropdown.tsx` — unused
- `LaptopScrollTransition.tsx` — unused
- `face_analytics.py` — legacy Haar cascade, superseded by YuNet in evidence_detectors.py

### 3.9 Low: Reference Projects in Root
- `VigilAI-Smart-Border-Surveillance-System-main/` — separate project with weapon detection
- `AI-Driven-Border-Security-and-Strategic-System-main/` — separate project
- `hub-main/` — separate project with model zoo (safety, vehicles, face, weapon models)
- These contain duplicate yolov8n.pt files and potentially useful weapon/vehicle models

---

## 4. DATABASE / DATA-MODEL PROBLEMS

| Problem | Impact | Priority |
|---------|--------|----------|
| Single `event_logs` table with JSON payload | No relational queries, no integrity | CRITICAL |
| No `cameras` table | Camera config lost on restart | CRITICAL |
| No `zones` table | Zone config lost on restart | CRITICAL |
| No `incidents` table | No incident lifecycle, no dedup | CRITICAL |
| No `global_entities` table | No cross-camera identity persistence | HIGH |
| No `local_tracks` table | No track history, no trajectory query | HIGH |
| No `evidence` table | Evidence not linked to incidents | HIGH |
| No `face_observations` table | Face data not queryable | MEDIUM |
| No `plate_observations` table | ANPR data not queryable | MEDIUM |
| No `weapon_observations` table | Weapon data not queryable | MEDIUM |
| No `camera_transitions` table | Cross-camera links not persisted | MEDIUM |
| No `threat_assessments` table | Threat history not queryable | MEDIUM |
| No Alembic migrations | Schema changes require manual intervention | MEDIUM |
| `global_person_id` not a DB column | Cross-camera identity not queryable | HIGH |

---

## 5. DATASET / MODEL ORGANIZATION PROBLEMS

### 5.1 Dataset Issues
- ✅ **Canonical `dataset/` directory** — established with 3 subdirs (surveillance, perimeter, drone)
- ✅ **`dataset/surveillance/`** — VIRAT surveillance dataset (CCTV + thermal + night + face detection)
- ✅ **`dataset/drone/`** — VisDrone MOT benchmark (UAV aerial surveillance)
- ✅ **`dataset/perimeter/`** — MOT17 MOT benchmark (ground-level perimeter tracking)
- **`datasets/`** — empty placeholder (legacy, can be removed)
- ✅ **Dataset registry** — `dataset/README.md` with sources/licenses
- **No master scenario test suite** for end-to-end validation

### 5.2 Model Issues
- **No canonical model directory structure** — spec requires `models/{object_detection,face,anpr,ocr,weapon,drone,reid}/`
- **OpenVINO model** in `models/yolov8n_openvino_model/` — unused by backend
- **No weapon detection model** in active use (gun.pt exists in VigilAI reference project)
- **No drone detection model** in active use
- **No model documentation** (name, version, source, license, classes, performance)

### 5.3 Runtime / Generated Files
- **`storage/`** — 2.98 GB of uploads, snapshots, evidence (mixed with source)
- **`percepta.db`** — 42.4 MB at repository root (should be in `runtime/` or `database/`)
- **`scratch/`** — 64 entries of debug scripts, logs, intermediate DBs
- **`frontend/dist/`** — build output present despite .gitignore

---

## 6. OVERSIZED FILES

| File | Lines | Issue |
|------|-------|-------|
| `backend/tracking/pipeline.py` | 859 | Detection + tracking + zone + evidence + alert in one file |
| `backend/detection/evidence_detectors.py` | 526 | Face + plate + OCR in one file |
| `backend/events/store.py` | 270+ | Event persistence + querying |
| `backend/intelligence/assistant.py` | 300+ | NL query + response building |
| `frontend/Landing.tsx` | 949 | 8 inline chapter components |
| `frontend/CameraFeed.tsx` | 770 | Viewport + zone drawing + replay |
| `frontend/AddCameraModal.tsx` | 591 | Upload + RTSP + webcam |
| `frontend/AlertInspector.tsx` | 491 | Evidence + chain + telemetry |
| `frontend/Dashboard.tsx` | 515 | Orchestrator + inline components |

---

## 7. DUPLICATED / DEAD CODE

| Item | Location | Status |
|------|----------|--------|
| `TiltCard.tsx` | frontend/components/ | UNUSED — superseded by PremiumCard |
| `MagneticButton.tsx` | frontend/components/ | UNUSED |
| `LogoDropdown.tsx` | frontend/components/ | UNUSED |
| `LaptopScrollTransition.tsx` | frontend/components/ | UNUSED |
| `face_analytics.py` | backend/detection/ | LEGACY — superseded by YuNet |
| `yolov8n.pt` | VigilAI reference project | DUPLICATE of models/yolov8n.pt |
| `ThreatGauge` | Dashboard.tsx | RENDERED TWICE with identical props |
| WebSocket connections | Dashboard + AlertPanel | DUPLICATE connections |
| Raw `fetch()` calls | AddCameraModal.tsx | BYPASSES api client |

---

## 8. PROPOSED RESTRUCTURING

### 8.1 Target Directory Structure
```
percepta-defense/
├── backend/
│   ├── api/                    (13 routers — keep, minor refactors)
│   ├── ingestion/              (10 adapters — keep as-is)
│   ├── detection/              (split: object/, face/, plate/, weapon/, drone/)
│   ├── tracking/               (split: local/, global/)
│   ├── entities/               (NEW: global entity management)
│   ├── zones/                  (keep, add persistence)
│   ├── events/                 (keep, add normalized event contract)
│   ├── risk/                   (rename intelligence/threat_engine)
│   ├── incidents/              (REBUILD: lifecycle, dedup, grouping)
│   ├── alerts/                 (NEW: operator-facing alert engine)
│   ├── evidence/               (extract from events/snapshots + detection/evidence_detectors)
│   ├── identity/               (extract from intelligence/)
│   ├── ai/                     (rename intelligence/assistant)
│   ├── storage/                (NEW: file storage management)
│   └── config/                 (NEW: centralized configuration)
├── frontend/
│   ├── pages/                  (keep, split oversized)
│   ├── components/             (split oversized, remove dead)
│   ├── features/               (NEW: cameras/, tracking/, incidents/, evidence/, alerts/, defense-ai/)
│   ├── hooks/                  (keep, add WebSocketProvider)
│   ├── services/               (NEW: API abstraction layer)
│   └── contexts/               (NEW: shared state providers)
├── dataset/                    (NEW: canonical dataset directory)
│   ├── surveillance/           (VIRAT, MOTH, UCF-Crime)
│   ├── perimeter/              (iLIDS, border intrusion)
│   ├── face/                   (detection, recognition)
│   ├── vehicle/                (detection, tracking)
│   ├── anpr/                   (plate datasets)
│   ├── weapon/                 (detection, validation)
│   ├── drone/                  (detection, validation)
│   └── master_scenarios/       (end-to-end test scenarios)
├── models/                     (reorganize by purpose)
│   ├── object_detection/       (yolov8n)
│   ├── face/                   (yunet)
│   ├── anpr/                   (plate detector + OCR)
│   ├── ocr/                    (PP-OCRv3)
│   ├── weapon/                 (future)
│   ├── drone/                  (future)
│   └── reid/                   (osnet)
├── runtime/                    (NEW: generated files)
│   ├── evidence/
│   ├── snapshots/
│   ├── clips/
│   ├── logs/
│   └── cache/
├── database/                   (NEW: schema + migrations)
│   ├── migrations/             (Alembic)
│   ├── schema/                 (DDL definitions)
│   └── seed/                   (test data)
├── tests/                      (keep, expand)
├── config/                     (NEW: centralized config)
├── scripts/                    (keep, clean debug scripts)
└── docs/                       (NEW: documentation)
```

### 8.2 Migration Strategy
1. **Do NOT delete the existing database** — back up first
2. **Add new tables** alongside existing `event_logs` — dual-write during transition
3. **Migrate data** from `event_logs.payload` JSON to normalized tables
4. **Update backend** to read from new tables
5. **Remove old `event_logs`** after validation

---

## 9. IMPLEMENTATION PHASES AND DEPENDENCIES

| Phase | Description | Depends On | Estimated Effort |
|-------|-------------|------------|-----------------|
| **PHASE 0** | Inspection + Assessment | — | ✅ DONE |
| **PHASE 1** | Architecture Foundation (normalize IDs, interfaces, schemas, config) | Phase 0 | HIGH |
| **PHASE 2** | Repository/Data Restructure (dataset/, models/, runtime/, database/) | Phase 1 | MEDIUM |
| **PHASE 3** | Database Redesign (new tables, migration, dual-write) | Phase 1 | HIGH |
| **PHASE 4** | Ingestion + Detection (stabilize adapters, normalize detection output) | Phase 1 | LOW |
| **PHASE 5** | Local Tracking (stable camera-local tracks) | Phase 4 | LOW |
| **PHASE 6** | Global Entity / Cross-Camera (global IDs, transitions, topology) | Phase 3, 5 | HIGH |
| **PHASE 7** | Zones + Events (state transitions, normalized event contract) | Phase 3 | MEDIUM |
| **PHASE 8** | Threat / Risk (dynamic, explainable, configurable) | Phase 7 | MEDIUM |
| **PHASE 9** | Specialized AI (weapon, face, ANPR, drone integration) | Phase 4 | MEDIUM |
| **PHASE 10** | Incident Engine (group events → incidents, lifecycle, dedup) | Phase 7, 8 | HIGH |
| **PHASE 11** | Alert Engine (one incident → one alert, escalation) | Phase 10 | MEDIUM |
| **PHASE 12** | Evidence (target-specific, incident-linked) | Phase 10, 12 | MEDIUM |
| **PHASE 13** | UI (Tactical Incident Feed, timelines, profiles, evidence viewer) | Phase 11, 12 | HIGH |
| **PHASE 14** | Grounded Defense AI (structured retrieval, FACT/INFERENCE/UNKNOWN) | Phase 6, 10 | MEDIUM |
| **PHASE 15** | Testing/Performance (master scenarios, stress tests) | All | HIGH |
| **PHASE 16** | Cleanup/Review (dead code, duplicates, security, docs) | All | LOW |

---

## 10. RISKS AND DEPENDENCIES

| Risk | Mitigation |
|------|-----------|
| Database migration may lose existing data | Dual-write during transition, backup before migration |
| Breaking existing API contracts | Version API endpoints, maintain backward compatibility |
| Frontend refactoring may break working UI | Incremental refactoring, test each component change |
| Weapon/drone models not available | Document as missing, integrate when available |
| Large dataset downloads may fail | Document sources, do not auto-download |
| Performance regression during refactor | Benchmark before/after each phase |
| Reference projects (VigilAI, hub-main) may have useful code | Inspect and extract before cleanup |

---

## 11. END-TO-END PIPELINE TRACE (AS-IS)

```
Frame (numpy array)
  → ObjectDetector.detect() → List[DetectionResult] (class, bbox, confidence)
  → ByteTrackTracker.update() → List[TrackedObject] (track_id, bbox, class)
  → ZoneMonitor.check_position() → Optional[ZoneEvent] (zone_id, transition)
  → [Evidence Detectors: YuNet face, Plate YOLOv8n, PP-OCRv3]
  → EventStore.record_events_batch() → SQLite INSERT → EventBus.publish()
  → [ThreatEngine] → RiskEvent (threat_score, factors)
  → [Alert creation] → AlertEvent (severity, message)
  → WebSocket broadcast → AlertPanel.prepend()
```

**Missing from pipeline:**
- No global entity assignment (Re-ID exists but not wired into pipeline)
- No incident grouping (each event is独立)
- No alert deduplication
- No target-specific evidence linking
- No camera topology awareness
- No entity profiles

---

**Assessment complete. Ready to proceed with PHASE 1 — Architecture Foundation.**
