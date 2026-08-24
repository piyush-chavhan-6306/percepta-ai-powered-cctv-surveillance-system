# BORDER INTELLIGENCE — COMPLETE DEMO EXECUTION KNOWLEDGE

**Project**: Border Intelligence (PS SIH26187)  
**Demonstration Target**: Live Judge Evaluation for Smart India Hackathon PS SIH26187  
**Verification Status**: 🟢 **8 / 8 Preflight Subsystems PASS | VIRAT Live CCTV Demo PASS**  

---

## 1. Demo Preflight Verification (`scripts/demo_preflight.py`)

The preflight check verifies that all hardware, directories, weights, database tables, and AI components are primed before a demonstration.

### Execution Command:
```bash
.\venv\Scripts\python scripts/demo_preflight.py
```

### Verified Subsystems (8 / 8 Matrix):
1. **Storage & Dirs**: Validates `models/`, `datasets/`, `storage/`, and `storage/snapshots/` directories exist and are writable.
2. **Database (WAL)**: Connects to SQLite and confirms `PRAGMA journal_mode = WAL` is active.
3. **YOLOv8 Model**: Loads `models/yolov8n.pt` local weights offline with zero internet dependency.
4. **Demo Video**: Confirms high-resolution VIRAT real CCTV dataset is present (`datasets/VIRAT_sample.mp4` - 156 MB).
5. **Frame Capture**: Reads test frame and confirms 1280x720 resolution decoding.
6. **AI Detection & Tracking**: Executes sample inference through YOLOv8n and ByteTrack association.
7. **Intelligence Engine**: Performs test grounded retrieval query and verifies 3-tier synthesis.
8. **EventBus Subsystem**: Verifies in-memory async message dispatch queue.

---

## 2. Live CCTV End-to-End Demonstration (`scripts/run_demo.py`)

The live demo runs the full perception-to-grounded-intelligence pipeline against real VIRAT CCTV surveillance footage.

### Execution Command:
```bash
.\venv\Scripts\python scripts/run_demo.py
```

### 6-Stage Execution Sequence:

#### Stage 1: Subsystem & SQLite WAL Initialization
- Initializes async SQLite database engine.
- Spawns in-memory EventBus.

#### Stage 2: CCTV Ingestion Registration
- Registers camera `CAM-01` ("Sector Alpha North Gate") pointing to `datasets/VIRAT_sample.mp4`.
- Bounded ring buffer initialized (capacity: 60 frames).

#### Stage 3: Perimeter Geometries Configuration
- Loads Polygon Security Zone: `Alpha Restricted Perimeter` (`[[200, 100], [1000, 100], [1000, 650], [200, 650]]`, loitering threshold: `1.5s`).
- Loads Virtual Tripwire Boundary: `North Perimeter Fence Line` (`[300, 350]` → `[900, 350]`, severity: `CRITICAL`).

#### Stage 4: AI Perception Pipeline Initialization
- Loads YOLOv8n detector with confidence threshold `0.35`.
- Initializes ByteTrack multi-target Kalman tracker with frame stride `2`.

#### Stage 5: Ingesting & Processing 40 Surveillance Frames
- Ingests real video frames.
- Identifies **9 unique persistent tracked targets** (Track IDs: `1` through `9`).
- Detects **12 to 14 perimeter security alerts** (Entry alerts & loitering dwell alerts exceeding 1.5s).
- Measures un-averaged AI processing throughput (15.6 FPS on CPU).

#### Stage 6: Grounded Intelligence Q&A Demonstration
Executes 3 operator natural-language queries:

1. **Query 1**: `"Show recent security alerts."`
   - `[OBSERVED FACT]`: Lists recent alert timestamps and track IDs.
   - `[DETERMINISTIC RULE RESULT]`: Links alerts to restricted zone thresholds.
   - `[AI INTERPRETATION / SUMMARY]`: Summarizes perimeter infractions.

2. **Query 2**: `"Which camera generated alerts in Sector Alpha?"`
   - Demonstrates camera sector filtering with zero hallucination.

3. **Query 3**: `"What happened in the restricted zone?"`
   - Aggregates event activity breakdown across tracking, zone entries, and alerts.
