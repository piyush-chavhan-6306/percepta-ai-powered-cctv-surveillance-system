# Border Intelligence — Performance Baseline Profiling Report

**Project**: Border Intelligence — AI-Powered Video Analytics Platform for Border Surveillance Using Existing CCTV  
**SIH Problem Statement**: PS SIH26187 ("AI-Based Intelligent Video Analytics Platform for Border Surveillance using existing CCTV Infrastructure")  
**Date**: 2026-08-23  
**Benchmark Test Stream**: `VIRAT/CCTV 01/VIRAT_S_000205_02_000409_000566.mp4` (100 frames, 1280x720 @ 30.0 FPS)  
**Execution Environment**: Single-Core Intel/AMD CPU (64-bit Windows)

---

## 1. Latency Breakdown by Pipeline Stage

| Pipeline Stage | Mean Latency (ms/frame) | % of Total Time | Assessment |
| :--- | :---: | :---: | :--- |
| **1. Video Decoding (OpenCV)** | $3.11\text{ ms}$ | $5.3\%$ | Fast; native OpenCV decode |
| **2. YOLOv8n Inference & NMS** | $\mathbf{43.51\text{ ms}}$ | $\mathbf{74.6\%}$ | **PRIMARY BOTTLENECK (74.6% of runtime)** |
| **3. ByteTrack Multi-Object Tracking** | $2.72\text{ ms}$ | $4.7\%$ | Extremely efficient; Kalman + Hungarian |
| **4. Security Zone & Loitering Rules** | $0.10\text{ ms}$ | $0.2\%$ | Deterministic ray-casting is near zero overhead |
| **5. Event Schema Creation** | $0.10\text{ ms}$ | $0.2\%$ | Pydantic model instantiations |
| **6. SQLite WAL Persistence** | $6.24\text{ ms}$ | $10.7\%$ | Secondary overhead (individual event commits) |
| **7. EventBus Publishing** | $<0.01\text{ ms}$ | $0.0\%$ | In-memory asyncio callback dispatch |
| **8. MJPEG JPEG Encoding** | $2.54\text{ ms}$ | $4.4\%$ | Lightweight JPEG frame compression |
| **Total Mean Frame Latency** | $\mathbf{58.35\text{ ms}}$ | $\mathbf{100.0\%}$ | **Current Baseline Throughput: 17.11 FPS (Raw Core)** |

---

## 2. Key Findings & Optimization Targets

1. **YOLOv8n Inference is 74.6% of all compute**:
   - At default input resolution ($640\text{px}$), CPU forward pass takes $\approx 43.5\text{ ms}$.
   - Class filtering is currently done in Python loop over all candidate boxes instead of passing `classes=[...]` directly to Ultralytics native NMS kernel.
   - Using `imgsz=512` or `imgsz=480` can reduce inference compute substantially while preserving detection accuracy for fixed CCTV surveillance.
   - Adaptive frame processing (`frame_stride=2`) skips redundant detection on intermediate frames while maintaining ByteTrack state, cutting effective inference time by ~50%.

2. **SQLite WAL Persistence is 10.7% of compute**:
   - `record_events_batch` or sharing session transactions per frame instead of opening multiple individual sessions per frame will reduce DB commit overhead from $6.24\text{ ms}$ to $<1.5\text{ ms}$.

3. **Remaining Components (<15% combined)**:
   - Tracking ($2.72\text{ ms}$), Zone calculations ($0.10\text{ ms}$), and EventBus ($<0.01\text{ ms}$) are already well-optimized and should not be modified.
