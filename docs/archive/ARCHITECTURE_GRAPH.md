# BORDER INTELLIGENCE — GRAPHIFY ARCHITECTURAL KNOWLEDGE GRAPH

**Project**: Border Intelligence — AI Border Surveillance Platform (PS SIH26187)  
**Graph Nodes**: 42 Production Modules, 42 Test Modules, 14 Demonstration Scripts, 8 Frontend Views  
**Baseline Test Verification**: 🟢 **130 / 130 Automated Tests Passing**  

---

## 1. High-Level Dependency Graph (Mermaid)

```mermaid
graph TD
    subgraph INGESTION["1. Ingestion Layer"]
        RTSP[rtsp_adapter.py]
        VIDEO[video_adapter.py]
        SIM[simulation_adapter.py]
        FBUF[frame_buffer.py]
        CAMMGR[camera_manager.py]
        OPTIC[optical_diagnostics.py]
        RTSP --> FBUF
        VIDEO --> FBUF
        SIM --> FBUF
        CAMMGR --> RTSP
        CAMMGR --> VIDEO
        CAMMGR --> SIM
    end

    subgraph PERCEPTION["2. Perception & Tracking Layer"]
        YOLO[detector.py]
        MODEL[model_loader.py]
        BYTE[bytetrack_wrapper.py]
        MOVE[movement.py]
        PIPE[pipeline.py]
        FBUF --> PIPE
        PIPE --> MODEL
        PIPE --> YOLO
        PIPE --> BYTE
        PIPE --> MOVE
    end

    subgraph SPATIAL["3. Spatial & Threat Rules"]
        ZONE[security_zone.py]
        TEMPL[templates.py]
        HEAT[heatmap.py]
        THREAT[threat_engine.py]
        PIPE --> ZONE
        ZONE --> TEMPL
        ZONE --> HEAT
        PIPE --> THREAT
    end

    subgraph PERSISTENCE["4. Persistence & EventBus Layer"]
        STORE[events/store.py]
        BUS[events/bus.py]
        DB[database.py]
        MODELS[incidents/models.py]
        FOR[events/forensics.py]
        AUDIT[events/audit_logger.py]
        SNAP[events/snapshots.py]
        PIPE --> STORE
        STORE --> DB
        STORE --> MODELS
        STORE --> BUS
        STORE --> FOR
        STORE --> AUDIT
        STORE --> SNAP
    end

    subgraph INTELLIGENCE["5. Grounded Intelligence Layer"]
        ASSIST[intelligence/assistant.py]
        STORE --> ASSIST
    end

    subgraph APILAYER["6. FastAPI REST & WebSocket Routers"]
        MAIN[main.py]
        APICAM[api/cameras.py]
        APIALERT[api/alerts.py]
        APIINC[api/incidents.py]
        APIZONE[api/zones.py]
        APIINTEL[api/intelligence.py]
        APISTREAM[api/streaming.py]
        APISYS[api/system.py]
        APISENS[api/sensors.py]
        APIEXP[api/export.py]
        MAIN --> APICAM
        MAIN --> APIALERT
        MAIN --> APIINC
        MAIN --> APIZONE
        MAIN --> APIINTEL
        MAIN --> APISTREAM
        MAIN --> APISYS
        MAIN --> APISENS
        MAIN --> APIEXP
    end

    subgraph FRONTEND["7. Command Center Frontend (React SPA)"]
        UI_DASH[DashboardView]
        UI_SURV[SurveillanceView]
        UI_INC[IncidentsView]
        UI_ZONE[ZonesView]
        UI_THREAT[ThreatView]
        UI_FOR[ForensicsView]
        UI_SENS[SensorsSystemView]
        UI_INTEL[IntelligenceView]
        APILAYER -.->|HTTP REST & WS| FRONTEND
    end
```

---

## 2. High-Centrality Hub Modules & Blast Radiuses

| Module Path | Centrality Score | Inbound Dependents | Outbound Dependencies | Blast Radius Level | Architectural Role |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `backend/events/store.py` | **1.00** | 18 | 6 | 🔴 **CRITICAL** | Core persistence engine enforcing Persist-Before-Publish contract across SQLite WAL |
| `backend/events/schema.py` | **0.95** | 22 | 2 | 🔴 **CRITICAL** | Canonical Pydantic event contracts utilized across all routers and pipelines |
| `backend/database.py` | **0.92** | 16 | 3 | 🔴 **CRITICAL** | Async SQLAlchemy engine, WAL PRAGMA configuration, sessionmaker |
| `backend/tracking/pipeline.py`| **0.88** | 12 | 8 | 🔴 **CRITICAL** | End-to-end multi-threaded tracking, prediction, and spatial evaluation orchestration |
| `backend/ingestion/camera_manager.py`| **0.82** | 10 | 6 | 🟠 **HIGH** | Fleet camera registration, reconnect backoff worker, stream broker |
| `backend/intelligence/assistant.py`| **0.80** | 4 | 5 | 🟠 **HIGH** | Grounded Q&A engine and security refusal guardrails |
| `backend/zones/security_zone.py` | **0.78** | 8 | 4 | 🟠 **HIGH** | Ray-casting polygon containment and line segment crossing algorithm |
| `backend/events/bus.py` | **0.75** | 7 | 2 | 🟡 **MEDIUM** | In-memory asyncio Pub/Sub message broker with client isolation |
| `backend/config.py` | **0.72** | 14 | 1 | 🟡 **MEDIUM** | Global environment variables and operational thresholds |

---

## 3. Dependency Hubs vs Leaf Modules

### Core Dependency Hubs (Upstream Providers)
- `backend/database.py`: Root DB session factory.
- `backend/events/schema.py`: Root type system.
- `backend/config.py`: Root application configuration.

### Intermediate Processing Engines
- `backend/tracking/pipeline.py`: Ingestion + Detection + Tracking + Spatial evaluation.
- `backend/events/store.py`: Disk persistence + Transaction retry + EventBus dispatch.
- `backend/intelligence/assistant.py`: Query retrieval + 3-tier synthesis.

### Leaf Routers & Adapters (Downstream Consumers)
- `backend/api/*.py`: 13 HTTP routers exposing services to external consumers.
- `frontend/src/views/*.tsx`: 8 presentation views consuming the REST/WS API layer.
