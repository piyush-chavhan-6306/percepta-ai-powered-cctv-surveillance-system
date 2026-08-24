# AGENT_CONTEXT.md — MASTER INSTRUCTION FILE FOR AI AGENTS

**CRITICAL INSTRUCTION FOR ALL FUTURE AI AGENTS**:
Read this document FIRST before writing code, modifying files, or planning tasks in this repository.

---

## 1. Project Identity & Problem Statement

- **Project Name**: Border Intelligence — AI-Powered Persistent Border Surveillance & Incident Intelligence Platform
- **Problem Statement**: Smart India Hackathon (SIH) Problem Statement **PS SIH26187**
- **Core Goal**: Transform existing legacy CCTV and IP camera infrastructure into an intelligent, real-time perimeter surveillance platform featuring automated intrusion detection, loitering analysis, tamper-proof forensic persistence, and grounded natural-language intelligence.

---

## 2. Current Verified Baseline (Frozen State)

- 🟢 **Automated Tests**: **130 / 130 PASSED** (`pytest -v` across 42 test files)
- 🟢 **Preflight Subsystems**: **8 / 8 PASSED** (`scripts/demo_preflight.py`)
- 🟢 **Live Demo**: **PASSED** (`scripts/run_demo.py` on real VIRAT CCTV footage)
- 🟢 **Frontend**: **Vite React TypeScript Command Post Live** (`http://localhost:5173/`)
- 🟢 **Backend Codebase**: **FROZEN**. Zero modifications to core perception, tracking, persistence, event bus, or existing APIs are authorized unless fixing a verified contract-breaking defect.

---

## 3. "Do Not Break" Core Invariants

1. **Persist-Before-Publish**:
   - Database writes to SQLite WAL must commit before events are broadcast across the EventBus or WebSockets (`backend/events/store.py`).
2. **Camera-Local Track IDs**:
   - Centroids and Track IDs (`Track 17`) are valid ONLY within a single camera's field of view. Do NOT implement speculative cross-camera re-ID without calibrated 3D extrinsics and human confirmation.
3. **Strict 3-Tier Grounded AI Outputs**:
   - The Natural-Language Intelligence Assistant MUST output clearly separated `[OBSERVED FACT]`, `[DETERMINISTIC RULE RESULT]`, and `[AI INTERPRETATION / SUMMARY]`. Never present LLM summaries as raw unverified facts.
4. **Anti-Hallucination Guardrails**:
   - Queries requesting biometric facial identity, weapon presence, subjective criminal intent, or arbitrary SQL execution must return immediate structured refusals (`grounding_status="refusal"`).
5. **RTSP Password Sanitization**:
   - Never log, expose, or return raw RTSP passwords over REST APIs. Passwords must be sanitized via `sanitize_rtsp_url()`.

---

## 4. Key Directory & Module Map

| Component | Path | Description |
| :--- | :--- | :--- |
| **FastAPI App** | `backend/main.py` | Mounts 13 routers, lifespan startup/shutdown |
| **Config & Settings** | `backend/config.py` | Pydantic BaseSettings, environment variables |
| **Database Engine** | `backend/database.py` | Async SQLAlchemy 2.0 engine, SQLite WAL PRAGMAs |
| **Event Persistence** | `backend/events/store.py` | `EventStore` class, atomic batch commits, retry backoff |
| **Event Schemas** | `backend/events/schema.py` | Pydantic contracts (`BaseEvent`, `TrackingEvent`, `ZoneEvent`, `AlertEvent`) |
| **Pub/Sub Bus** | `backend/events/bus.py` | In-memory async EventBus with isolated subscriber queues |
| **Tracking Pipeline** | `backend/tracking/pipeline.py` | `TrackingPipeline`, frame stride, Kalman prediction |
| **ByteTrack Wrapper** | `backend/tracking/bytetrack_wrapper.py` | Association matrix, Kalman tracking algorithm |
| **Perception Detector**| `backend/detection/detector.py` | Offline YOLOv8n inference, class filtering |
| **Perimeter Zones** | `backend/zones/security_zone.py` | Ray-casting point-in-polygon containment, tripwires, loitering |
| **Grounded Assistant**| `backend/intelligence/assistant.py` | `ControlledQueryLayer`, 3-tier synthesis, refusal guardrails |
| **Threat Engine** | `backend/intelligence/threat_engine.py` | DEFCON 1-4 real-time scoring matrix (0–100) |
| **Frontend Root** | `frontend/src/App.tsx` | React SPA layout, context provider, 8 operational views |

---

## 5. API Quick Reference (47 Endpoints)

- **Health & Diagnostics**: `GET /api/health`, `GET /api/readiness`, `GET /api/system/status`, `GET /api/system/metrics`, `GET /api/system/coverage-report`, `GET /api/system/db-diagnostics`, `POST /api/system/demo-reset`
- **Cameras**: `GET /api/cameras`, `POST /api/cameras/register`, `GET /api/cameras/{id}`, `POST /api/cameras/{id}/start`, `POST /api/cameras/{id}/stop`, `POST /api/cameras/{id}/reconnect`, `DELETE /api/cameras/{id}`, `GET /api/cameras/{id}/diagnostics`, `GET /api/cameras/{id}/heatmap`
- **Alerts & Incidents**: `GET /api/alerts`, `POST /api/alerts/{id}/ack`, `GET /api/incidents`, `GET /api/incidents/{id}/timeline`, `GET /api/incidents/{id}/dossier`, `GET /api/incidents/{id}/notes`, `POST /api/incidents/{id}/notes`
- **Security Zones**: `GET /api/zones`, `POST /api/zones`, `POST /api/zones/boundary`, `DELETE /api/zones/{id}`, `GET /api/zones/templates`, `POST /api/zones/apply-template`
- **Threat & Forensics**: `GET /api/threat/level`, `GET /api/evidence/verify/{id}`, `GET /api/evidence/audit-integrity`, `GET /api/evidence/snapshots/{id}`, `GET /api/events/export`
- **Multi-Modal Sensors**: `GET /api/sensors/status`, `POST /api/sensors/ingest`
- **Intelligence Query**: `POST /api/intelligence/query`
- **Streaming**: `GET /api/stream/video/{id}`, `GET /api/stream/raw/{id}`, `WebSocket /ws/events`

---

## 6. How to Run Verifications

```bash
# 1. Run Complete 130 Automated Tests
.\venv\Scripts\pytest -v

# 2. Run Preflight Subsystem Checks
.\venv\Scripts\python scripts/demo_preflight.py

# 3. Run Live VIRAT CCTV Demo
.\venv\Scripts\python scripts/run_demo.py

# 4. Build Frontend Bundle
cd frontend && npm run build
```

---

## 7. How to Launch Servers

```bash
# Terminal 1: Backend
.\venv\Scripts\uvicorn backend.main:app --host 127.0.0.1 --port 8000

# Terminal 2: Frontend
cd frontend && npm run dev -- --host
```
