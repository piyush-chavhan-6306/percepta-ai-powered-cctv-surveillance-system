# BORDER INTELLIGENCE — FUTURE IMPLEMENTATION ROADMAP

**Project**: Border Intelligence (PS SIH26187)  
**Architecture Status**: Backend Frozen (130/130 Tests Passing), Command Center Frontend Live  
**Roadmap Scope**: Phased Engineering Roadmap for AI Coding Agents & Product Evaluators  

---

## 1. Roadmap Phasing Overview

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ PHASE 1: FRONTEND & COMMAND CENTER UI ──► [ 🟢 COMPLETED & VERIFIED ]                  │
│ • React + TypeScript + Vite SPA, 8 Operational Views, WebSocket Live Telemetry        │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ PHASE 2: ADVANCED OPERATOR WORKFLOWS ──► [ 🟡 READY FOR IMPLEMENTATION ]              │
│ • Multi-monitor popout video walls, native OS sound alerts, QRF Telegram/SMS dispatch │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ PHASE 3: CALIBRATED MULTI-CAMERA INTELLIGENCE ──► [ 🔵 ARCHITECTURAL BOUNDARY DEFINED] │
│ • Extrinsics calibration, overlapping FOV homography, appearance Re-ID, human review   │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ PHASE 4: MULTI-MODAL SENSOR FUSION ──► [ 🔵 PROTOCOL EXTENSION ]                       │
│ • Kalman fusion of ground seismic vibrations, radar tracks, and thermal IR centroids   │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ PHASE 5: ENTERPRISE DEPLOYMENT & SCALING ──► [ 🔵 INFRASTRUCTURE READY ]              │
│ • Docker compose, Kubernetes Helm, PostgreSQL 15+ asyncpg migration                    │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ PHASE 6: EDGE COMPRESSION & ACCELERATION ──► [ 🔵 HARDWARE OPTIMIZATION ]              │
│ • TensorRT INT8 quantization, DeepStream GStreamer pipeline on NVIDIA Jetson Orin      │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Detailed Phase Specifications

### Phase 1: Frontend / Command Center (COMPLETED)
- **Status**: 🟢 **Completed & Verified**
- **Deliverables**: React SPA, 8 Views (Dashboard, Feeds, Incidents, Zones, Threat, Forensics, Sensors, Intelligence), WebSocket client, MJPEG player.
- **Verification**: `npm run build` passing, 130/130 backend tests passing.

---

### Phase 2: Advanced Operator Workflows
- **Feature Name**: Operational Notification & Dispatch Integrations
- **Why It Exists**: To allow command post operators to instantly alert deployed Quick Reaction Teams (QRF) via cellular/radio protocols upon verified perimeter breaches.
- **User Value**: Drastically cuts response time from initial detection to ground interception.
- **Dependencies**: `backend/incidents/annotations.py`, `backend/events/bus.py`
- **Files Likely to Change**: `backend/api/incidents.py`, `frontend/src/views/IncidentsView.tsx`
- **API Requirements**: `POST /api/incidents/{id}/dispatch`
- **Risk Level**: Low (does not alter frozen CV perception pipeline).
- **Implementation Order**: Priority 1.

---

### Phase 3: Calibrated Multi-Camera Intelligence (Architectural Boundary)

> [!IMPORTANT]
> **STRICT ARCHITECTURAL INVARIANT**:
> Camera-local Track IDs are authoritative today. Speculative cross-camera re-identification based on raw visual prompts alone is prohibited to prevent false arrests and mission failures.

#### Non-Negotiable Prerequisites for Future Cross-Camera Re-ID:
1. **Geometric Extrinsics Calibration**: Known GPS coordinates and 3D camera extrinsics $(X, Y, Z, \text{yaw}, \text{pitch}, \text{roll})$ for all camera pairs.
2. **Overlapping FOV Homography**: Pre-computed ground-plane homography matrices between adjacent sectors.
3. **Hardware Time Synchronization**: Microsecond PTP / NTP time synchronization across all edge encoders.
4. **Appearance Embeddings**: Validated deep Re-ID feature extractor (e.g. OSNet / FastReID) with cosine distance thresholding.
5. **Confidence Score & Uncertainty Quantification**: Explicit distance metric (e.g., $d < 0.25$) attached to all handoff candidates.
6. **Mandatory Human Verification**: Operator confirmation prompt before merging incident tracks across sectors.

---

### Phase 4: Multi-Modal Sensor Fusion
- **Feature Name**: Radar + Seismic + Thermal IR Kalman Sensor Fusion
- **Why It Exists**: Optical CCTV cameras suffer degraded visibility during sandstorms, heavy fog, blackout nights, and dense foliage.
- **User Value**: Continuous all-weather target tracking even when optical camera vision is 100% blinded.
- **Current Status**: Tier-B Multi-Modal schemas and ingestion endpoint implemented (`POST /api/sensors/ingest`).
- **Next Step**: Implement Central Track Fusion Manager utilizing Extended Kalman Filters (EKF) across spatial radar coordinates and camera bounding boxes.
- **Files to Change**: `backend/sensors/fusion_manager.py`, `backend/tracking/pipeline.py`

---

### Phase 5: Enterprise Deployment Infrastructure
- **Feature Name**: PostgreSQL 15+ Migration & Kubernetes Cluster Packaging
- **Why It Exists**: High-availability clustering across regional border command headquarters.
- **Current Status**: Certified in `backend/database_diagnostics.py` with standard SQLAlchemy ORM models.
- **Deployment Plan**:
  - `docker-compose.yml`: Multi-container stack (FastAPI backend, PostgreSQL + TimescaleDB, Redis, React frontend, Nginx reverse proxy).
  - Helm Chart: Stateless backend pods with persistent volume claims for model weights and video recordings.

---

### Phase 6: Edge Hardware Acceleration & Model Quantization
- **Feature Name**: TensorRT INT8 Acceleration for Edge Outposts
- **Why It Exists**: Maximize FPS and battery efficiency on solar-powered border surveillance pods (NVIDIA Jetson AGX Orin / Xavier).
- **Optimization Strategy**: Export YOLOv8n to TensorRT engine (`yolov8n.engine`) using FP16/INT8 calibration caches.

---

## 3. Biometric / Face Recognition Policy Boundary

> [!CAUTION]
> **RESTRICTED CAPABILITY**:
> Biometric facial recognition is explicitly out of scope for general border CCTV infrastructure due to resolution constraints (perimeter cameras capture targets at 50–500m where face resolution is $< 15 \times 15$ pixels), high false-positive rates in adverse weather, and strict privacy/defense regulations.
> 
> The system operates strictly on bounding-box centroids, spatial velocities, and perimeter polygon containment. Any future biometric module must be an isolated, policy-controlled add-on requiring explicit human officer authorization.
