# PERCEPTA — Running the Hybrid Edge-Cloud System

## Architecture

```
┌─────────────────────────────────────────┐
│          LOCAL MACHINE (Edge)            │
│                                         │
│  FastAPI Edge (port 8000)               │
│   ├─ Camera Manager                     │
│   ├─ YOLO v8n (ONNX)                   │
│   ├─ ByteTrack + Kalman                 │
│   ├─ ANPR / Face / Weapon               │
│   ├─ Zones / Tripwires                  │
│   ├─ Threat Engine                      │
│   ├─ Incidents / Evidence               │
│   ├─ SQLite WAL (local DB)              │
│   └─ WebSocket /ws/events               │
│                                         │
│  [Optional] ngrok tunnel                │
│   └─ https://xxxx.ngrok-free.app        │
└───────────────────┬─────────────────────┘
                    │ Internet (optional)
                    ▼
┌─────────────────────────────────────────┐
│         Vercel Cloud C2                 │
│  percepta.vercel.app                    │
│   ├─ Static React frontend              │
│   ├─ Auth (FastAPI JWT / offline local) │
│   └─ Reads edge URL from localStorage  │
└─────────────────────────────────────────┘
```

**INTERNET IS OPTIONAL FOR CORE SURVEILLANCE.**  
The edge node runs YOLO, tracks entities, and stores incidents locally regardless of network status.

---

## Quick Start

### 1. Offline Mode (Local Only)

```bat
# Activate virtualenv
venv\Scripts\activate.bat

# Start the edge
python start_edge.py
```

Access the local C2: **http://127.0.0.1:8000**

---

### 2. Online Mode (Vercel C2 → Live YOLO)

You need a free [ngrok account](https://ngrok.com/) for this.

```bat
# Set your ngrok auth token (one-time)
set NGROK_AUTHTOKEN=your_token_here

# Activate virtualenv
venv\Scripts\activate.bat

# Start edge with public tunnel
python start_edge.py --tunnel
```

The script will print:

```
==============================
  PERCEPTA EDGE — ONLINE MODE ACTIVE
==============================
  Local FastAPI:   http://127.0.0.1:8000
  Public URL:      https://abcd1234.ngrok-free.app
  ...
```

Then in the Vercel C2 (percepta.vercel.app):
1. Click the **PROBING / OFFLINE / LOCAL** badge in the top-right header
2. Paste the ngrok URL
3. Click **TEST** → **APPLY**

The C2 will now reach live YOLO inference through the tunnel.

---

### 3. Make It Permanent (Vercel env var)

For a permanent connection (e.g., dedicated server or static tunnel):

```bash
vercel env add VITE_API_URL https://your-stable-edge-url.com production
vercel --prod
```

---

## Credentials (Default)

| Username   | Password       | Role            |
|------------|---------------|-----------------|
| `operator` | `operator123` | Duty Officer    |
| `commander`| `commander123`| Sector Commander|
| `admin`    | `admin123`    | Administrator   |

Offline fallback: any username containing `operator`, `admin`, or `commander` works without the backend.

---

## Model Files (must be present)

| Model | Path | Required |
|-------|------|---------|
| YOLOv8n ONNX | `models/detection/yolov8n.onnx` | ✅ Yes |
| YOLOv8n PT | `models/detection/yolov8n.pt` | Optional |
| ANPR Plate | `models/anpr/plate_yolov8n.onnx` | Optional |
| ANPR OCR | `models/anpr/en_PP-OCRv3_rec_infer.onnx` | Optional |
| Face Detection | `models/face/face_detection_yunet_2023mar.onnx` | Optional |
| Re-ID | `models/reid/osnet_x0_25_msmt17.onnx` | Optional |
| Weapon | `models/weapon/gun.pt` | Optional |

---

## Operational Modes (Dashboard Header Badge)

| Badge | Meaning |
|-------|---------|
| 🟡 PROBING | Initial connectivity check in progress |
| 🟢 LOCAL EDGE | Connected to FastAPI at 127.0.0.1:8000 |
| 🔵 ONLINE | Connected to remote edge via configured URL |
| 🔴 OFFLINE | No backend reachable — demo data only |

Click the badge to open the Edge Setup modal.
