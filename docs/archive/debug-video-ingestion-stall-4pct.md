# Debug Session: video-ingestion-stall-4pct

**Status**: [OPEN] INSTRUMENTATION PHASE
**Created**: 2026-09-10
**Bug Summary**: Video ingestion/playback through the surveillance pipeline stalls consistently around 4% progress.

---

## 1. Falsifiable Hypotheses

| ID | Hypothesis | Predicted Evidence | Falsification |
|---|---|---|---|
| H1 | RTSP real-time pacing / `time.sleep` applied to VIDEO_FILE sources causes throttling | Timing logs show `sleep(N)` between frames proportional to 1/FPS, wall-clock matches media-time exactly up to stall, CPU is mostly idle | sleep log shows 0ms between frames for VIDEO_FILE, CPU is pegged |
| H2 | Frame buffer / queue deadlock: ingestion producer blocks on `queue.put(full)` while consumer (worker) is stuck on downstream processing | `queue_size == max_size` repeatedly at stall time; ingestion thread state = WAITING on queue.put; worker thread alive but last_processed_frame == stall_frame | queue_size is small / empty, ingestion thread continues reading |
| H3 | Progress/metadata bug: CAP_PROP_FRAME_COUNT is inflated by codec but frame_number is correct | Logged frame_number advances linearly; logged progress_pct = frame/total stalls at ~4% but total is 25× actual | progress_pct increases if recomputed with a validated total |
| H4 | cap.read() returns ret=False near 4%; EOF/reconnect logic loops on the same bad offset | Repeated `read FAILED ret=False` at the same frame_number ~X; no frame_count increase beyond X; reconnect tries same position and fails again | ret=True continuously, no failed-read log lines |
| H5 | ANPR/evidence/OCR runs synchronously inline and blocks on first vehicle (≈4% into footage) | stall_frame == first_vehicle_detection_frame; evidence_ms / anpr_ms jumps to huge value or ∞; worker alive but stuck inside process_evidence/plate_aggregator | stall happens before any vehicle is detected |

---

## 2. Instrumentation Plan

2.1. VideoAdapter: read_ret_ok, read_ret_fail, cap_props (total_frames, fps, codec), frame_number, media_ts, progress_pct, pre_read_sleep_ms, post_read_sleep_ms, loop_state
2.2. CameraWorker / LiveWorker: ingest_fps, inference_fps, tracking_ms, reid_ms, evidence_ms, anpr_ms, encode_ms, queue_size (before put / after get), ingestion_alive, worker_alive
2.3. Progress reporter: periodic 1s heartbeat log = frame/TOTAL, media_ts, progress%, all FPS and latency components, queue states, thread alive states
2.4. EventStore / PersistBeforePublish: persist_latency_ms, on stalled frame check if last_seq_id is advancing
2.5. WS / MJPEG: if backend frame_number advances but frontend shows 4%, it's UI progress bug (H3 or streaming issue)

---

## 3. Pre-Fix Evidence

TBD

---

## 4. Root Cause Determination

TBD — confirmed hypothesis after reproduction with instruments.

---

## 5. Fix

TBD — minimal patch.

---

## 6. Post-Fix Evidence / Acceptance

TBD — 0% → 100% full run metrics.

---

## 7. Before/After Performance Report

TBD
