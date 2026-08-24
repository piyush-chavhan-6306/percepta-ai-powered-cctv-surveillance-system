# Resume notes — MVP real-tracking rebuild

Working branch: `feat/mvp-real-tracking`
Last commit: `e488fa4` (Phase 1 groundwork). Baseline snapshot is `254e253`.
Spec being implemented: `MVP_REBUILD_PROMPT.md` (§0–§8, AC1–AC6).

## State: clean

- Working tree clean, nothing uncommitted.
- `.\venv\Scripts\python -m pytest -q` → **139 passed** (identical to baseline; no
  contracts changed yet).
- No server left running; port 8000 free.
- Scratch files from baseline verification removed.

## Baseline facts, verified by running the app (not from the docs)

All three bugs in §1 were confirmed empirically before any code was touched:

1. `frontend/src/components/CameraCard.tsx` fakes detections — hardcoded
   `TRK-01`/`TRK-04` at lines 30-33, moved by `Math.sin`/`Math.cos` in the
   100 ms interval at lines 52-76, over a static `/videos/border-demo.mp4`.
2. No perception runs on the server. `TrackingPipeline.process_frame` is called
   only from `scripts/run_demo.py`, never from a route or background task.
3. `backend/api/streaming.py::_mjpeg_generator` JPEG-encodes raw frames with no
   annotation. Registered `CAM-BASE` on the VIRAT clip and pulled 287 frames in
   6 s (~47.8 fps, i.e. no pacing at all); the saved frame had **zero boxes** and
   the DB had **zero events** for that camera.

Bounding-box contract, confirmed before writing the renderer:
`TrackedObject.bounding_box` is `[x1, y1, x2, y2]` in **source-frame pixels**
(there is a separate `normalized_box`). Zone polygons are `[(x, y), ...]` pixels;
`VirtualBoundary` is `pt1`/`pt2` pixels.

## What Phase 1 groundwork already landed (e488fa4)

- `backend/tracking/overlay.py` — `draw_zones` / `draw_tracks` / `draw_hud`,
  plus `annotate_frame(...)` and `encode_jpeg(...)`. Predicted (stride-skipped)
  boxes draw dashed + dimmed.
- `backend/ingestion/webcam_adapter.py` — `WebcamAdapter` for AC2.
- `pipeline.py` — `_detect_async()` runs YOLO via `asyncio.to_thread` behind an
  optional shared `inference_lock`; `_record_latency()` bounds `_recent_latencies`
  (was a genuine ~2M floats/day leak).
- `video_adapter.py` / `rtsp_adapter.py` — `read_frame_blocking()` extracted from
  `get_next_frame()`; async signatures deliberately unchanged.
- `camera_manager.py` — reads offloaded to a thread; single-owner rule documented
  on `get_latest_frame`.

## Next action (pick up exactly here)

The Phase-1 smoke test was mid-run when we stopped. It fails only on test
harness setup, **not** on the new code: `TrackingPipeline` persists events, and
`backend/events/store.py` requires `await init_db()` first
(`backend/database.py:58` raises `RuntimeError: Database must be initialized via
init_db() before obtaining sessions`). Fix the script by awaiting
`init_db("sqlite+aiosqlite:///smoke_test.db")` before `process_frame`, then
re-run. It writes `smoke_040/080/119.jpg` for visual inspection — delete those
and `smoke_test.db*` afterwards, they are scratch.

Then build the real thing, in this order:

1. **`backend/tracking/live_worker.py`** — per-camera `CameraWorker` + registry.
   It is the *single owner* of the frame source (§4). Loop: read frame →
   `pipeline.process_frame` **every** frame (stride only skips YOLO, Kalman
   `predict_step` still yields boxes, so AC3 gets no stutter) → `annotate_frame`
   → `encode_jpeg` once → publish to `latest_annotated[camera_id]` with a
   sequence counter. Annotate + encode in a thread. Pace to source FPS.
2. **`ZoneMonitor.with_shared_definitions(source)`** — a per-worker monitor that
   shares the global `zones`/`boundaries` dicts *by reference* so zones created
   via `/api/zones` propagate live, while per-track state stays per camera.
   This matters: `bytetrack_wrapper.py` emits bare integer track IDs (`"1"`,
   `"2"`) with no camera namespace, and `ZoneMonitor` keys state by bare
   `track_id`, so one shared monitor across cameras would corrupt prev-position
   state and fire phantom tripwire crossings. Tests assert only ID *stability*,
   never the format, so this is safe.
3. **Rewrite `_mjpeg_generator`** to serve the worker's annotated JPEG and stop
   calling `get_latest_frame` itself (§4's frame-stealing trap). Cap clients.
4. **Wire worker start/stop** into `/api/cameras/register|start|stop`, `DELETE`,
   and `main.py` lifespan; cancel cleanly on shutdown. Auto-register one VIRAT
   clip on startup.
5. **`CameraCard.tsx`** → `<img src={api.getVideoStreamUrl(id)}>`; delete
   `activeDetections`, the sine/cos animation, the static-mp4 fallback, the
   hardcoded "RESTRICTED PERIMETER LINE", and the fake frame counter.

Verify AC1 + AC3 visually in the browser before moving on — §7 says Phase 1 is
the critical milestone and not to proceed until it's real.

## Still queued after that

- **Phase 2 (AC2)** — add `webcam` to `POST /api/cameras/register`; indefinite
  auto-reconnect with capped backoff; "SIGNAL LOSS" placeholder; long-run leak
  and handle check.
- **Phase 3 (AC4)** — seed a demo zone/tripwire sized to the camera's real
  resolution; confirm alerts arrive over WebSocket and persist.
- **Phase 4 (AC5)** — cut UI to Live Monitoring / Add Camera / Alerts; remove or
  clearly label simulated widgets (3D map, sensors, threat gauges, presentation
  mode, `lib/simulation/demoScenario.ts`). Replace the fabricated constants in
  `backend/api/system.py::/api/system/metrics` (`display_fps: 60.0`,
  `inference_latency_ms: 42.0`, etc.) with real pipeline telemetry — they
  violate §6. Fix three broken client paths: `/ack` → `/acknowledge`,
  `/incidents/{id}/timeline` → `/incidents/{id}`, and the dead
  `getRawStreamUrl`. (`frontend/src/src/` is already absent — nothing to delete.)
- **Phase 5 (AC6)** — `README_RUN.md`, explicit CORS for `http://localhost:5173`,
  re-run tests, full AC1–AC6 dry run.
