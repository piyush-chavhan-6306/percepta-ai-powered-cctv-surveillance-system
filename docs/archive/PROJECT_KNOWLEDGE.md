# BORDER INTELLIGENCE — MASTER PROJECT KNOWLEDGE BASE

**Project**: Border Intelligence — AI-Powered Persistent Border Surveillance & Incident Intelligence Platform  
**Official Problem Statement**: PS SIH26187 ("AI-Based Intelligent Video Analytics Platform for Border Surveillance using existing CCTV Infrastructure")  
**Current Baseline**: 🟢 **130 / 130 Automated Tests Passing (FROZEN)**  
**Demo Status**: 🟢 **8 / 8 Preflight Subsystems PASS | VIRAT Live Demo PASS**  
**Frontend Status**: 🟢 **Vite React TypeScript Command Post Live on Port 5173**  

---

## 1. Executive Summary & Mission

Border Intelligence is an edge-optimized, real-time computer vision and intelligence platform purpose-built for persistent perimeter monitoring across border outposts, forward operating bases (FOBs), and sensitive defense installations utilizing existing legacy CCTV and IP camera infrastructure.

### Core Mission Objectives:
1. **Zero-Hardware-Overhaul Ingestion**: Ingest standard RTSP, video files, and simulated surveillance feeds from commodity CCTV cameras without requiring specialized hardware.
2. **Deterministic AI Perception**: Real-time object detection (YOLOv8n) combined with persistent spatial tracking (ByteTrack) and Kalman filter trajectory prediction.
3. **Defense-in-Depth Spatial Rules**: Real-time evaluation of polygon restricted zones, virtual tripwire boundaries, directional headings, and loitering dwell timers.
4. **Persist-Before-Publish Guarantee**: Guaranteed SQLite WAL database persistence prior to asynchronous WebSocket broadcast, providing an unalterable chain-of-custody for all audit and forensic records.
5. **Grounded Natural-Language Intelligence**: Strict 3-tier explainable Q&A system eliminating generative hallucinations and providing provable evidence linkages for duty commanders.

---

## 2. Verified Architectural Tiers

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               TIER S — CORE ENGINE                                     │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ • Camera Lifecycle (RTSP / Video File / Simulation / Bounded Ring FrameBuffer)         │
│ • Local Offline AI Perception (YOLOv8n with Automatic CUDA / CPU Fallback)             │
│ • Multi-Target Persistent Tracking (ByteTrack + Kalman Intermediate State Prediction)  │
│ • Spatial Rule Engine (Polygon Containment, Virtual Tripwires, Loitering Clocks)       │
│ • Event Persistence (SQLite WAL, Monotonic Sequence IDs, Persist-Before-Publish)       │
│ • Real-time Broadcast (Async EventBus, Resilient WebSocket /ws/events, MJPEG Feeds)    │
│ • Grounded Intelligence Assistant (3-Tier Output, Strict Refusal Guardrails)           │
│ • Threat Engine (DEFCON 1-4 Real-Time Scoring Matrix, Contributing Factors)            │
│ • Forensic Evidence (SHA-256 Tokens, Incident Dossier / SitRep, 16x16 Spatial Heatmap) │
└────────────────────────────────────────────────────────────────────────────────────────┘
                                            │
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                           TIER A — OPERATIONAL ENABLERS                                │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ • Operator Incident Annotations & QRF Dispositions (POST/GET /api/incidents/{id}/notes)│
│ • Security Zone Tactical Templates (Border Strip, Gate Funnel, Fence Line Presets)     │
│ • Surveillance Coverage & Readiness Analytics Report (Combat Ready / Degraded Grades)  │
│ • Environmental Surveillance Sensitivity Profiles (Day, Night, Storm, Convoy Modes)    │
│ • Automated Visual Evidence Snapshot Archival (JPEG Stills & API Browser)             │
└────────────────────────────────────────────────────────────────────────────────────────┘
                                            │
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                         TIER B — POLISH & EXTENSIBILITY                                │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ • Administrative System Action Audit Logger (GET /api/system/audit-logs)               │
│ • Forensic Event Exporter (RFC 4180 CSV / Structured JSON Exporter)                    │
│ • Multi-Modal Sensor Ingestion (Radar, Seismic Vibrations, Thermal IR, RF Detector)   │
│ • Database WAL Diagnostics & Enterprise PostgreSQL Migration Certification             │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Directory Layout & Module Taxonomy

```
d:\SIH   border cctv\
├── backend/
│   ├── api/                    # 13 REST & WebSocket API Routers (47 Endpoints)
│   │   ├── alerts.py           # /api/alerts, /api/alerts/{id}/ack
│   │   ├── cameras.py          # /api/cameras CRUD, start, stop, diagnostics, heatmap
│   │   ├── events.py           # /api/events, /api/events/replay
│   │   ├── export.py           # /api/events/export (CSV / JSON)
│   │   ├── forensics.py        # /api/evidence/verify/{id}, /api/evidence/audit-integrity, snapshots
│   │   ├── health.py           # /api/health, /api/readiness
│   │   ├── incidents.py        # /api/incidents, timeline, dossier, operator notes
│   │   ├── intelligence.py     # /api/intelligence/query (3-Tier Grounded Q&A)
│   │   ├── sensors.py          # /api/sensors/ingest, /api/sensors/status
│   │   ├── streaming.py        # /api/stream/video/{id}, /api/stream/raw/{id}, /ws/events
│   │   ├── system.py           # /api/system/status, metrics, coverage-report, profiles, audit-logs, db-diagnostics, demo-reset
│   │   ├── threat.py           # /api/threat/level
│   │   └── zones.py            # /api/zones, boundaries, templates, template applicator
│   ├── detection/              # Offline YOLOv8 Detection Subsystem
│   │   ├── detector.py         # YOLODetector wrapper, class filtering, stride skipping
│   │   └── model_loader.py     # Local model cache, CPU/CUDA hardware detection
│   ├── events/                 # Event Store, EventBus, Cryptographic Forensics
│   │   ├── audit_logger.py     # Persistent administrative audit logging engine
│   │   ├── bus.py              # Async Pub/Sub EventBus with client isolation
│   │   ├── forensics.py        # SHA-256 verification and root hash chain auditing
│   │   ├── schema.py           # Typed Pydantic schemas (Detection, Tracking, Zone, Alert, System)
│   │   ├── snapshots.py        # Evidence snapshot image disk storage and lookup
│   │   └── store.py            # SQLite WAL EventStore (Persist-Before-Publish engine)
│   ├── incidents/              # Incident Aggregator, SitRep Dossier, Annotations
│   │   ├── annotations.py      # Operator notes & QRF disposition log
│   │   ├── dossier.py          # Tactical SitRep generator with motion vectors
│   │   └── models.py           # Incident aggregation memory state models
│   ├── ingestion/              # Multi-Protocol Video Ingestion Engine
│   │   ├── adapter.py          # Abstract Base Ingestion Adapter
│   │   ├── camera_manager.py   # Multi-camera registry, auto-reconnect backoff
│   │   ├── frame_buffer.py     # Lock-free bounded ring buffer
│   │   ├── optical_diagnostics.py # Laplacian focus, glare, and darkness evaluation
│   │   ├── rtsp_adapter.py     # RTSP IP camera stream adapter with credential masking
│   │   ├── simulation_adapter.py # Synthetic coordinate video frame generator
│   │   └── video_adapter.py    # Local MP4/AVI OpenCV video file adapter
│   ├── intelligence/           # Grounded AI Assistant & Threat Engine
│   │   ├── assistant.py        # Controlled query retrieval layer & anti-hallucination guardrails
│   │   └── threat_engine.py    # Deterministic DEFCON scoring engine (0-100)
│   ├── sensors/                # Defense Multi-Modal Sensors
│   │   └── multi_modal.py      # Radar, Seismic, Thermal IR, RF schemas & registry
│   ├── tracking/               # Multi-Target Tracking & Motion Prediction
│   │   ├── bytetrack_wrapper.py# ByteTrack association algorithm & Kalman filters
│   │   ├── movement.py         # Velocity vectors, cardinal headings, speeds
│   │   ├── pipeline.py         # End-to-end tracking pipeline orchestration
│   │   └── tracker.py          # TrackedObject data classes and trajectory histories
│   ├── zones/                  # Perimeter Defense Geometries
│   │   ├── heatmap.py          # 16x16 normalized spatial density matrix
│   │   ├── security_zone.py    # Ray-casting point-in-polygon containment & tripwires
│   │   └── templates.py        # Tactical defense presets library
│   ├── config.py               # Pydantic BaseSettings, environment variable configuration
│   ├── config_profiles.py      # Operational sensitivity profiles switcher
│   ├── database.py             # SQLAlchemy 2.0 async engine & SQLite WAL PRAGMAs
│   ├── database_diagnostics.py # SQLite storage diagnostics & PostgreSQL migration checks
│   └── main.py                 # FastAPI application factory and router mounting
├── frontend/                   # React + TypeScript + Vite Command Center SPA
├── scripts/                    # Demonstration, benchmarking, and preflight tools
├── tests/                      # 130 Unit, Integration, and Failure regression tests
└── border_intelligence.db      # SQLite WAL Production Database
```

---

## 4. Architectural Invariants (Non-Negotiable Contracts)

1. **Backend Freeze**: The core backend architecture, detection pipeline, ByteTrack tracking, SQLite WAL schema, event bus contracts, and REST/WebSocket APIs are fully verified across 130 tests and remain FROZEN.
2. **Persist-Before-Publish**: Under NO circumstances may an alert or incident event be dispatched over WebSockets before it is committed to disk in SQLite WAL (`EventStore.record_event`).
3. **Camera-Local Track IDs**: Track IDs are authoritative ONLY within a single camera's field of view. Cross-camera identity re-identification is strictly out of scope without calibrated camera extrinsics and human-in-the-loop verification.
4. **Anti-Hallucination Guardrails**: The Grounded Intelligence Assistant NEVER generates speculative claims. Outputs are strictly segmented into `[OBSERVED FACT]`, `[DETERMINISTIC RULE RESULT]`, and `[AI INTERPRETATION / SUMMARY]`.
5. **RTSP Credential Masking**: IP camera URLs containing authentication strings (e.g., `rtsp://admin:pass@ip:554`) are sanitized immediately upon ingestion and never logged or exposed via API.
