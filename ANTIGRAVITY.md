# ANTIGRAVITY — Execution Playbook

> Hand this file to the Antigravity coding agent as the first thing it reads.
> It is self-contained: what the project is, what is already done and verified,
> exactly how to run it, what to build next and in what order, and the rules
> that must not be broken. Everything here was verified against the code on
> **2026-08-24**, branch `feat/mvp-real-tracking`.

---

## 0. The one-paragraph brief

**Border Intelligence** (SIH PS **SIH26187**) is a border-surveillance MVP. An
operator opens a web app and sees **real CCTV/video with real detection +
tracking boxes** following real people and vehicles smoothly — including from a
live 24/7 camera. When a tracked object enters a drawn restricted zone or
crosses a tripwire, a **real alert** fires over WebSocket and is persisted. The
backend does the perception; the browser only displays frames the backend has
already annotated. **There must be no mock data, fake boxes, or simulated
overlays anywhere on the shipping path.**

The stack: **Python 3.13 / FastAPI / SQLAlchemy async + SQLite (WAL)** on the
backend; **Ultralytics YOLOv8n + ByteTrack + Kalman** for perception (CPU-only,
torch 2.13.0+cpu, no CUDA on this host); **React 19 / TypeScript / Vite /
Tailwind 4** on the frontend.

---

## 1. Current state — what is DONE and VERIFIED (do not rebuild)

The **backend perception path is complete and all 140 tests pass.** Committed on
`feat/mvp-real-tracking` (commits `14ad520` → `ca63f3b`). Do **not** rewrite
these; build on them.

- **`backend/tracking/live_worker.py`** — `CameraWorker` is the single owner of
  each camera's frame source. It reads → runs detection→tracking→zones → burns
  boxes into the frame → JPEG-encodes **once** → publishes a `LiveFrame` that
  all viewers fan out from. All blocking work is in `asyncio.to_thread`.
  Deadline-based pacing. Live sources reconnect indefinitely (SIGNAL LOSS card
  on drop). `WorkerRegistry` + `get_worker_registry()` singleton.
- **`backend/api/streaming.py`** — MJPEG endpoint serves the worker's
  already-annotated frames; it does **not** read the adapter (that would steal
  frames and halve both rates). Client cap + `finally` release. Also
  `/api/stream/snapshot/{id}` for a single JPEG.
- **`backend/api/cameras.py`** — register / **upload** / **webcam** / RTSP, each
  starts a real worker. `/sources/available` lists on-disk clips + uploads.
  start/stop/reconnect/deregister drive the registry in the correct order.
- **`backend/tracking/pipeline.py`** — adaptive-stride FPS math fixed (was
  double-counting stride and oscillating; delivered output went 8.2 → 19.2 fps).
  Per-track TRACKING-event sampling caps DB growth ~10× (alerts/zone events are
  never sampled). `ZoneMonitor.with_shared_definitions()` shares zone defs by
  reference, per-track state private.
- **`backend/api/system.py`** — `/api/system/metrics` now reports **measured**
  worker metrics, not the old hardcoded constants (this was the AC5 violation on
  the metrics endpoint).
- **`backend/events/store.py`** — 2 s TTL cache on the `COUNT(*)` scans that were
  stalling MJPEG up to ~1.9 s.
- **`backend/main.py`** — `bootstrap_demo_camera()` starts the bundled VIRAT clip
  as `CAM-01` on boot (best-effort). Lifespan stops workers before sources.

**Frontend is UNTOUCHED and is the main remaining work** (see §3).

---

## 2. How to run it (verified commands, Windows / Git Bash)

**Backend** (from repo root `D:\SIH   border cctv`):

```bash
./venv/Scripts/python -m uvicorn backend.main:app --port 8000
```

- Serves REST + WS on `http://127.0.0.1:8000`. On boot it auto-registers and
  starts `CAM-01` on the demo clip, so `GET /api/stream/video/CAM-01` is live
  immediately.
- If the demo clip is missing it logs a warning and boots anyway — add a camera
  from the UI.

**Frontend** (separate terminal):

```bash
cd frontend && npm install && npm run dev
```

- Vite dev server on `http://localhost:5173`. It talks to the backend at
  `http://127.0.0.1:8000` (override with `VITE_API_URL` / `VITE_WS_URL`).
- CORS is already allow-listed for `localhost:5173` and `4173`.

**Tests** (must stay green — 140 passing):

```bash
./venv/Scripts/python -m pytest tests/ -q
```

**The demo clip** the judges will see:
`VIRAT/CCTV 01/VIRAT_S_000205_02_000409_000566.mp4` (has small distant objects —
that is why inference size stays at 640).

---

## 3. What to build next — ordered by priority

Do these top-down. Each is independently shippable; commit after each.

### TASK A — Redesign the frontend UI (HIGHEST, explicitly requested)

The current UI is not acceptable and must be replaced with a **morphic /
adaptive** design, and useless features removed.

**Remove these views/components entirely** (they are demo theatre, and several
render fake data — an AC5 violation):
- `TacticalMap3D.tsx`, `ThreatGauge.tsx`, `ThreatBadge.tsx`,
  `PresentationMode.tsx`, `DemoControlModal.tsx`, `SensorsSystemView.tsx`,
  `SimulationDashboard.tsx`, `LandingView.tsx`, `ThreatView.tsx`.
- In `App.tsx` drop the corresponding `case` branches and the multi-modal-sensor
  / threat-gauge / presentation-mode wiring.

**Keep and rebuild around three surfaces:**
1. **Live Monitoring** — the camera grid. Each tile is
   `<img src={api.getVideoStreamUrl(id)}>` (an MJPEG `<img>`, **not** a
   `<video>`). **Delete all client-side overlay drawing** — no
   `activeDetections.map(...)`, no `%`-positioned boxes, no `sin/cos` animation.
   The boxes are already burned into the stream by the backend. This is the core
   AC5 fix.
2. **Add Camera** — form/modal calling `registerCamera` (video_file / webcam /
   rtsp), plus the **upload** path (`POST /api/cameras/upload`, multipart) and a
   picker fed by `GET /api/cameras/sources/available`.
3. **Alerts** — live list driven by the WebSocket (`WS_BASE_URL`) + REST
   `getAlerts`, with acknowledge.

**Morphic design language to apply** (adapt tastefully, don't over-animate a
security tool): fluid shifting gradients; components that transform on
interaction (a button that morphs into a slider when engaged, a dropdown that
expands into a searchable panel, a status indicator that expands into a chart);
cards that grow when frequently accessed; navigation that reorders by usage;
subtle cursor-proximity motion; responsive typography; layout that evolves with
use. Keep it legible and fast — no jank on the video grid.

**Verify after:** run backend + frontend, open `localhost:5173`, confirm boxes
track people on `CAM-01` smoothly, and that **no number/box/alert on screen is
fabricated** — every one traces to a real backend response.

### TASK B — Zone / boundary drawing UI (HIGH, part of the core pitch)

Let the operator draw a restricted zone (polygon) and a tripwire (line) on a
camera tile so crossing generates a real alert.

- Draw over the camera tile; capture clicks and **convert to source-frame
  pixels** using the `<img>` `naturalWidth`/`naturalHeight` vs its rendered
  size. The backend expects **pixel coordinates in the source frame**, not
  normalized or screen coords.
- POST polygon → `createZone` (`POST /api/zones`, body
  `{zone_id, name, polygon: [[x,y],...] (≥3), severity}`).
- POST line → `createBoundary` (`POST /api/zones/boundary`, body
  `{boundary_id, name, pt1:[x,y], pt2:[x,y], severity}`).
- List/delete via `getZones` / `deleteZone`. Templates exist
  (`/api/zones/templates`, `/api/zones/apply-template`) if useful.

> **Known gap to flag, not silently ignore:** zones/boundaries live **only in
> memory** in the global `ZoneMonitor` — there is no DB table and nothing
> reloads them on restart. For the MVP demo that is fine (draw them live). If
> persistence is wanted, add a small table + load-on-startup in
> `bootstrap_demo_camera`'s vicinity; the shared-monitor plumbing
> (`with_shared_definitions`) already makes a newly added zone take effect on
> every running camera immediately.

### TASK C — README_RUN.md + AC dry-run (MEDIUM)

Write a one-page `README_RUN.md`: prerequisites, the two run commands above, the
test command, and a 6-step judge walkthrough mapping to AC1–AC6 (§4). Then
actually walk AC1–AC6 once and note anything that doesn't hold.

### TASK D — Suspicious-movement alerts (MEDIUM, if time)

Loitering already exists (zone `loitering` transitions with a dwell threshold).
`backend/intelligence/threat_engine.py` exists but has not been audited — read
it before adding anything. Candidate heuristics on the tracks the pipeline
already produces: sudden direction reversal, abnormal speed, or perimeter
approach. Keep it grounded (derived from real track kinematics), persisted, and
surfaced as a real alert. Do not invent a "threat score" that isn't computed.

---

## 4. Acceptance criteria (this is the definition of done)

| # | Criterion | How to check |
|---|-----------|--------------|
| **AC1** | Real boxes + stable track IDs on the VIRAT demo clip | Open `CAM-01`; IDs persist as people move |
| **AC2** | Live camera auto-reconnects indefinitely | Register a webcam/RTSP; unplug it → SIGNAL LOSS → replug → recovers unattended |
| **AC3** | Smooth ≥~20 FPS; boxes must not stutter | Watch the stream; stride is allowed, motion stays smooth (Kalman-predicted on skipped frames) |
| **AC4** | Real alerts on zone entry / tripwire, over WS + persisted | Draw a zone, walk a track through it; alert appears live and in `getAlerts` |
| **AC5** | Clean MVP UI, **no fake data** | Every box/number/alert traces to a real backend response |
| **AC6** | One-command run + tests pass | The two run commands in §2; `pytest tests/ -q` → all green |

---

## 5. Rules that must not be broken

1. **No fake data on the shipping path.** Every box, number, and alert the
   operator sees comes from the real backend. This is the whole point of the
   project — it is why the metrics endpoint and the old CameraCard overlays were
   the two biggest defects.
2. **Keep tests green.** 140 pass right now. Only change a test if you
   intentionally change a contract, and **say so** in the commit body (there is
   one such deliberate change already: `test_tracking_pipeline.py` passes
   `tracking_event_interval_frames=1` to keep asserting per-frame telemetry).
3. **Keep the REST/WS contracts stable** unless a task requires otherwise; the
   frontend and tests depend on them.
4. **The worker is the single owner of each camera's frame source.** Never read
   the adapter from a second place (streaming, a new endpoint, a debug tool) —
   it steals frames and halves the rate. Consume `LiveFrame`s from the worker.
5. **Never block the event loop.** cv2 read / YOLO / annotate / encode go through
   `asyncio.to_thread`. Release `cv2.VideoCapture` on stop. Cap MJPEG clients.
6. **No per-frame memory growth.** Bounded buffers only (the latency window and
   the per-track event map are already bounded — follow that pattern).
7. **Inference stays offline / CPU-capable.** Use CUDA if present but never
   hard-fail without a GPU. `DEMO_MODE=True` bypasses strict WS token checks for
   judges.
8. **Small, verifiable commits.** One coherent change each, real message body.

---

## 6. Fast facts / gotchas (save yourself the rediscovery)

- **Stream URL:** `GET /api/stream/video/{camera_id}` → `multipart/x-mixed-replace`
  MJPEG, already annotated. `getVideoStreamUrl(id)` in `frontend/src/api/client.ts`.
- **Demo camera id:** `CAM-01`. Auto-started on boot via `AUTOSTART_DEMO_CAMERA`
  (config default `True`).
- **Zone coords are source-frame pixels**, polygon needs ≥3 points. Boundary is
  two points `pt1`/`pt2`.
- **Zones are in-memory only** (no persistence, no reload on restart) — see
  Task B note.
- **Track IDs are camera-local, bare integers** with no camera namespace. Do not
  assume they are globally unique or comparable across cameras (the assistant
  layer explicitly refuses cross-camera identity questions, and this was the
  root of a real test-isolation bug — a stress test leaking `track_id="17"`).
- **CPU-only host, ~38% background load.** Microbenchmarks are noisy here; the
  perf fixes are structural (deadline pacing, overhead accounting, stride math),
  not tuned constants. `MAX_FRAME_STRIDE=5`, `DEFAULT_FRAME_STRIDE=2`,
  `TARGET_FPS=25`.
- **SQLite is shared by all tests.** If you add a test that writes events, clean
  up your rows in a `finally` (see `test_exhaustive_verification.py`) — the DB is
  not isolated per test.
- **DB can bloat fast** if you disable event sampling; `border_intelligence.db`
  hit 154 MB / 248k rows in an hour before the per-track sampling fix. A large
  archived copy is under `storage/archive/` — ignore it.
- **oxlint** is the frontend linter; keep it clean.

---

## 7. Suggested order of attack for Antigravity

1. Read this file, then `git log --oneline -8` and skim the six recent backend
   commits to see the shape of the perception path.
2. Run backend + frontend (§2), open `localhost:5173`, and observe the current
   (unacceptable) UI against real `CAM-01` video so you know the starting point.
3. **Task A** (UI redesign + fake-data removal) — biggest user-visible win.
4. **Task B** (zone drawing) — completes the core alert story with AC4.
5. **Task C** (README_RUN + AC dry-run), then **Task D** if time remains.
6. Keep `pytest tests/ -q` green throughout; commit per task.
