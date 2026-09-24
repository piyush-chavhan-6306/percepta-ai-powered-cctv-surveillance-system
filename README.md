# PERCEPTA DEFENSE — AI Border & Perimeter Intelligence System

> **Tactical Autonomous Surveillance, Global Entity Tracking, and Threat Assessment Platform**  
> *Authoritative System Specification & Architectural Reference: [PERCEPTA_MASTER.md](file:///d:/SIH%20%20%20border%20cctv/PERCEPTA_MASTER.md)*

---

## 1. What is Percepta Defense?

Percepta Defense is an AI-powered border and perimeter surveillance intelligence platform. It transforms raw, fragmented optical and multi-modal sensor streams into real-time, actionable tactical intelligence for human operators and command center personnel.

Rather than flooding tactical operators with raw, noisy object bounding boxes, Percepta runs a deterministic multi-stage intelligence pipeline that correlates detections, maintains cross-camera spatial identity, assesses environmental risk context, groups related target actions into coherent **Incidents**, and enforces the **Killer Alert Invariant**:

$$\text{One Underlying Incident} \equiv \text{One Operator-Facing Alert}$$

---

## 2. Quick Architecture Summary

```
[Optical / Thermal / Drone / Seismic / Radar Sensors]
                       │
                       ▼
             [Ingestion Adapters]
                       │
                       ▼
            [Object Detection (YOLO)]
                       │
                       ▼
            [Local Tracking (ByteTrack)]
                       │
                       ▼
         [Global Entity Association (OSNet Re-ID)]
                       │
                       ▼
        [Spatial & Contextual Threat Evaluation]
                       │
                       ▼
             [Incident Assembler]
                       │
                       ▼
         [Alert Deduplication Engine]
                       │
                       ▼
[FastAPI Gateway + WebSocket Push + Grounded Defense AI]
```

- **Backend:** FastAPI (Python 3.13), SQLAlchemy 2.0 (Async/Sync), ByteTrack, TorchReID (OSNet x0.25), ONNX Runtime, OpenCV, PyTorch.
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, Lucide Icons, Recharts.
- **Database:** SQLite 3 (WAL mode, foreign key enforcement, 18 normalized tables).

---

## 3. Major Capabilities

| Capability | Description |
| :--- | :--- |
| **Cross-Camera Tracking** | Correlates target re-appearances across non-overlapping camera FOVs using 512-dim visual embeddings and spatial topology constraints. |
| **5-Band Threat Assessment** | Evaluates target proximity, velocity vectors, zone classification (CRITICAL/WARNING/SAFE), tripwire crossing, and loitering (`INFORMATIONAL`, `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`). |
| **Alert Deduplication** | Emits a single primary alert per incident, appending target observations, tracks, and timeline checkpoints without operator notification spam. |
| **Follow-Track Seeking** | Generates an chronological cross-camera journey for any global entity, with sub-second timeline seeking across raw footage and keyframe crops. |
| **ANPR & Face Analytics** | Detects license plates (CRNN/OCR) and facial feature crops without storing biometric templates or making identity assertions. |
| **Multi-Modal Diagnostics** | Ingests auxiliary fence vibration, seismic sensors, and optical camera tamper metrics (blur, occlusion, glare). |
| **Grounded Defense AI** | Strictly deterministic spatial query engine (`backend/intelligence/assistant.py`) answering operational queries exclusively using confirmed database records. Zero hallucination. |

---

## 4. Quick Start & Development Commands

### Prerequisites
- Python 3.10+ (Recommended: Python 3.11–3.13)
- Node.js 18+ & npm
- FFmpeg (for video decoding and RTSP streaming)

### Backend Setup
```bash
# Activate virtual environment
.\venv\Scripts\Activate.ps1    # Windows PowerShell
# source venv/bin/activate     # Linux/macOS

# Install dependencies
pip install -r requirements.txt

# Start backend server (Port 8000)
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend Setup
```bash
cd frontend

# Install dependencies
npm install

# Start Vite dev server (Port 5173)
npm run dev

# Build for production
npm run build
```

---

## 5. Testing Commands

The repository maintains an exhaustive test suite covering unit logic, failure recovery, camera lifecycle, and end-to-end integration:

```bash
# Run all backend unit and integration tests (233 passing tests)
pytest tests/ -q

# Run with verbose output
pytest tests/ -v

# Run specific intelligence test suites
pytest tests/unit/test_grounded_defense_ai.py
pytest tests/unit/test_movement_intelligence_and_threats.py
pytest tests/unit/test_camera_lifecycle.py

# Check frontend TypeScript compilation & build
cd frontend
npm run build
```

---

## 6. Important System Limitations

1. **Deterministic Edge Processing:** Grounded Defense AI relies on local structured SQL queries; it is intentionally offline and does not call external cloud LLM APIs.
2. **Camera Overlap Constraints:** Camera re-identification performance depends on calibrated camera topology (`backend/topology/`); uncalibrated cameras rely solely on visual feature embeddings.
3. **Hardware Acceleration:** Inference runs at ~45–90 FPS on CUDA-enabled GPUs. On CPU-only environments, throughput depends on thread allocation and batch sizes.
4. **Non-Attributive Surveillance:** System identifies *targets*, *intruding entities*, and *threat indicators*; it never outputs subjective assertions of criminality or guilt.

---

## 7. Master Documentation & Integration Reference

For complete engineering specifications, relational database schemas, API contracts, WebSocket protocols, and FreeBuf UI integration guidelines, consult:

👉 **[PERCEPTA_MASTER.md](file:///d:/SIH%20%20%20border%20cctv/PERCEPTA_MASTER.md)** (Authoritative Source of Truth)
