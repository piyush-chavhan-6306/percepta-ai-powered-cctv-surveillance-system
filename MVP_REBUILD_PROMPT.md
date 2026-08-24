# Claude Code Task — Make Border Intelligence a Working MVP (Real Tracking + Live 24/7 Camera + Clean UI)

> Paste this whole file to Claude Code, or run `claude` inside `D:\SIH   border cctv` and say:
> **"Read MVP_REBUILD_PROMPT.md and execute it. Work in phases, verify each phase by actually running the app, and don't move on until the acceptance criteria for that phase pass."**

---

## 0. Role & prime directive

You are a senior full-stack + computer-vision engineer. This repo LOOKS finished (dozens of "everything passes" markdown reports, 130 green unit tests) but the **core feature has never actually worked in the running app**. Your job is to make it genuinely work, be smooth, and look like a clean MVP.

**Prime directive:** The operator must open the web app and see **real video with real detection + tracking boxes that follow real people/vehicles**, smoothly, including from a **live camera running continuously (24/7)**. No mock data, no fake boxes, no "simulated" overlays anywhere in the shipping UI. If something is simulated, it must be clearly labeled and must not be the primary demo path.

**Trust the code and the running app, NOT the markdown docs.** The ~40 `.md` audit/report files in the repo (PROJECT_AUDIT.md, DEMO_KNOWLEDGE.md, *_FREEZE.md, etc.) describe intent and overclaim reality. Verify everything by running it.

---

## 1. The bug (already diagnosed — verify, then fix)

Confirm each of these before you start (grep + read the cited files), then fix them:

1. **Frontend boxes are fake.** `frontend/src/components/CameraCard.tsx` initializes `activeDetections` with hardcoded `TRK-01 / TRK-04` boxes and animates them with `Math.sin()/Math.cos()` timers. The `<video>` source is a static looping file (`/videos/border-demo.mp4`). It never consumes real detections and never uses the backend stream.
2. **The live server runs NO perception.** `TrackingPipeline.process_frame()` (`backend/tracking/pipeline.py`) and `TrackedObject` are real and correct — but `process_frame` / `TrackingPipeline(...)` are referenced in **only one place**: `scripts/run_demo.py`. **No API route or background task ever calls the pipeline.** So under `uvicorn`, YOLO + ByteTrack never run.
3. **MJPEG serves raw frames.** `backend/api/streaming.py::_mjpeg_generator` pulls `get_latest_frame` and JPEG-encodes it with **no boxes drawn**. And nothing on the frontend even requests this endpoint.

Net effect: detection/tracking works in a throwaway script and in unit tests, but the actual product shows a static video with cartoon boxes. That is the entire problem.

---

## 2. Definition of done (acceptance criteria)

Ship when ALL of these are true and you've verified them by running the app:

- [ ] **AC1 — Real boxes on recorded video:** Register one of the VIRAT clips (e.g. `VIRAT/CCTV 01/VIRAT_S_000205_02_000409_000566.mp4`). In the browser, boxes with track IDs are drawn on the actual moving people/vehicles, produced by the real YOLOv8n + ByteTrack pipeline. IDs stay stable across frames.
- [ ] **AC2 — Live camera 24/7:** Add a live source (laptop webcam `device 0`, or an RTSP URL). The feed shows real-time detection/tracking and keeps running indefinitely; if the camera drops, it auto-reconnects without a server restart. Memory/handles do not leak over a long run.
- [ ] **AC3 — Smooth:** Displayed video looks smooth (target ≥ ~20 FPS display). Detection may run on a stride (every Nth frame) but boxes must not stutter — reuse last/predicted boxes on in-between frames.
- [ ] **AC4 — Real alerts:** When a tracked object enters a configured zone / crosses a tripwire, a real alert appears live in the UI (driven by backend events over WebSocket), and is persisted.
- [ ] **AC5 — Clean MVP UI:** The UI is simplified to the core (see §5). No fake/hardcoded detections, no dead buttons, no lorem-ipsum panels. It looks intentional and uncluttered.
- [ ] **AC6 — One-command run:** There is a documented, reliable way to start backend + frontend (a short `README_RUN.md` or npm/py script). Backend tests that still apply pass.

---

## 3. Environment & how to run (Windows)

- Backend venv: `.\venv\Scripts\python` and `.\venv\Scripts\pip`.
- Start backend: `.\venv\Scripts\python -m uvicorn backend.main:app --reload --port 8000` (confirm the actual app path in `backend/main.py`).
- Frontend: `cd frontend && npm install && npm run dev` (Vite, usually port 5173).
- Model weights already present: `models/yolov8n.pt`. Keep inference **offline** (no downloads at runtime).
- Confirm `.env` / `backend/config.py`: enable the WebSocket **DEMO_MODE** bypass (see `validate_ws_token` in `backend/gateway/dependencies.py`) so the frontend can connect without a JWT, and make sure CORS allows the Vite origin (`http://localhost:5173`). A broken WS auth/CORS path is a likely reason panels stay empty.
- Verify GPU vs CPU: `ObjectDetector(device=...)` — use CUDA if available, else CPU. Don't hard-fail if no GPU.

---

## 4. Target architecture — the reliable way to get smooth real boxes

Do **server-side annotated MJPEG** as the primary video path. This is the single most robust approach for a demo because the boxes are burned into the exact frame the browser shows — zero client-side coordinate/timestamp syncing, nothing to drift, "video but no boxes" becomes impossible.

Implement a **single ingestion+inference loop per camera** (one owner of the frame source — do NOT let two consumers both call `get_latest_frame`, or they'll steal frames from each other):

```
per-camera async task (started when camera starts):
  loop while running:
    frame = adapter.get_next_frame()          # single owner of the source
    result = pipeline.process_frame(frame)     # YOLOv8n + ByteTrack (real)
    annotated = draw_overlays(frame.image, result.tracks, zones, tripwires)
    latest_annotated[camera_id] = annotated    # shared slot (thread/async safe)
    # tracking/zone/alert events are already persisted+published inside process_frame
```

Then:
- **Rewrite `_mjpeg_generator`** to serve `latest_annotated[camera_id]` (JPEG-encode the annotated frame). It must NOT call `get_latest_frame` itself anymore.
- **`draw_overlays`**: use OpenCV (`cv2.rectangle`, `cv2.putText`, `cv2.line`, `cv2.polylines`). Verify the exact `bounding_box` format first (read `backend/detection/detector.py` and `backend/tracking/tracker.py` / `bytetrack_wrapper.py` — likely `[x1,y1,x2,y2]` in pixels). Draw box + `ID + class + conf`, draw configured zone polygons and tripwire lines, and optionally a short trajectory trail from `TrackedObject` history.
- **Smoothness:** keep `frame_stride` so YOLO runs every Nth frame, but the loop still emits an annotated frame every frame using ByteTrack's Kalman `predict_step` boxes on in-between frames (the pipeline already supports `enable_intermediate_predictions`). Tune stride to hit AC3.
- Keep the existing **WebSocket `/api/ws/events`** broadcasting real `TrackingEvent`/`AlertEvent` (already wired via EventBus + `emit_tracking_events=True`). The frontend uses it for the live alert feed and counters. (Client-side canvas overlay on top of a raw stream is an optional enhancement — do the annotated-MJPEG path first because it always works.)

**Frontend video tile:** replace the fake-box logic in `CameraCard.tsx` with a simple `<img src="http://localhost:8000/api/stream/video/{camera_id}">` (MJPEG renders directly in an `<img>`). Remove `activeDetections`, the sine/cos animation, and the static-mp4 fallback. Keep a tasteful HUD (camera name, live FPS from `/api/system/metrics` or the WS, status).

**Camera lifecycle:** start/stop the per-camera loop from the camera register/start/stop routes (`backend/api/cameras.py`, `system.py`) and from `backend/main.py` lifespan for any auto-started demo camera. Ensure loops are cancelled cleanly on shutdown and on deregister.

---

## 5. UI — cut to a clean MVP

The current UI has 10 views and lots of decorative/fake content. Collapse to the core and make it feel intentional (a calm, dark operations console; good spacing; one accent color; readable mono for data; no flashing gimmicks). Keep or add only:

1. **Live Monitoring (primary):** grid of live annotated feeds (1 / 4 / 9 layout). Each tile = real MJPEG stream + minimal HUD. This is the money screen — it must look great and run smooth.
2. **Add Camera:** one clean modal with three real options — **Webcam (device 0)**, **RTSP/IP URL**, **Local video file** (pick from the VIRAT clips or upload). Registering must actually start the per-camera loop.
3. **Alerts / Incidents (secondary):** a live list fed by real WebSocket events, click an item to see details (timestamp, camera, track, snapshot). Reuse existing incident/alert APIs; drop anything that renders fabricated rows.

Remove, hide behind a small "More" menu, or clearly mark as simulated: the 3D tactical map, multi-modal sensors, threat gauges, presentation mode, etc. Do not let simulated widgets sit on the main path pretending to be real. Delete the orphaned `frontend/src/src/` duplicate folder.

You may consult the repo's design tokens in `frontend/src/index.css`, but prioritize clarity and smoothness over decoration.

---

## 6. Constraints & guardrails

- **No fake data in the shipping UI.** Every number/box/alert on the primary path must come from the real backend. If you need a fallback, label it and keep it off the main demo path.
- **Don't break what passes.** Keep backend REST/WS contracts stable where the frontend depends on them. Run the existing test suite (`.\venv\Scripts\python -m pytest -q`); keep tests green (update tests only if you intentionally change a contract, and say so).
- **Work in small, verifiable commits.** Suggested branch: `feat/mvp-real-tracking`. Commit per phase.
- **Performance & stability:** no per-frame memory growth; release `cv2.VideoCapture` on stop; cap MJPEG clients; the inference loop must not block the event loop (run YOLO in a thread executor if needed).
- **MVP discipline:** don't gold-plate. Get AC1→AC6 solid before any extra polish.

---

## 7. Suggested phase order (verify by running after each)

- **Phase 1 — Prove the core on one recorded clip (AC1, AC3).** Add the per-camera loop + `draw_overlays` + annotated MJPEG, point `CameraCard` at it, auto-register one VIRAT clip on startup. Open the browser: confirm real boxes track real people smoothly. This is the critical milestone — do not proceed until it's real.
- **Phase 2 — Live camera 24/7 (AC2).** Add/confirm a webcam adapter (`cv2.VideoCapture(0)`) and RTSP path; wire auto-reconnect (camera_manager already has `reconnect_camera`). Run it for a while; confirm no leaks and auto-recovery.
- **Phase 3 — Real alerts (AC4).** Ensure zone/tripwire evaluation runs in the live loop and the UI alert feed updates live from WebSocket events.
- **Phase 4 — UI cleanup to MVP (AC5).** Simplify views per §5, remove fake widgets, delete the duplicate `src/src/` folder, tidy the add-camera flow.
- **Phase 5 — Run docs + final pass (AC6).** Write a short `README_RUN.md` (exact start commands + how to add a webcam). Re-run tests. Do a final smooth-demo dry run of all acceptance criteria.

---

## 8. First actions for you (Claude Code)

1. Print the repo layout for `backend/` and `frontend/src/` and open: `backend/main.py`, `backend/api/streaming.py`, `backend/api/cameras.py`, `backend/tracking/pipeline.py`, `backend/tracking/bytetrack_wrapper.py`, `backend/detection/detector.py`, `backend/ingestion/camera_manager.py`, `backend/ingestion/rtsp_adapter.py`, `backend/gateway/dependencies.py`, and `frontend/src/components/CameraCard.tsx`.
2. Confirm the 3 bugs in §1 and the exact `bounding_box` coordinate format.
3. Get the app running as-is (backend + frontend) and confirm current behavior (static video, fake boxes) so you have a baseline.
4. Then start Phase 1. Report what you verified visually after each phase.
