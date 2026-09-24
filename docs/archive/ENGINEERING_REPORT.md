# PERCEPTA Border Intelligence — Engineering Report
## All 11 Phases (A→J) Complete

**Date**: September 10, 2026  
**Backend**: `http://localhost:8000` | **Frontend**: `http://localhost:5000`  
**Status**: ALL PHASES PASS | 7/7 videos regression PASS | 0 errors

---

## Summary of Fixes Applied

### Fix 1: Track ID Instability (Phase A+B)
**Root cause**: Cross-class NMS threshold (0.60) too high for small objects. YOLO per-class NMS let twin boxes through (bus+truck on same vehicle), ByteTrack spawned sibling tracks.

| Metric | Before | After | Change |
|---|---|---|---|
| Unique track IDs | 69 | 54 | -22% |
| Duplicate IDs (<30px) | 580 | **0** | -100% |
| NMS suppression rate | 2% | 16% | +8x |
| Track churn rate | 0.12/frame | 0.09/frame | -25% |

**Changes**: `bytetrack_wrapper.py` — lowered IoU threshold 0.60→0.40 (0.25 for vehicle pairs), added `deduplicate_tracks()` post-ByteTrack spatial dedup.

### Fix 2: Evidence Capture (Phase A)
**Root cause**: Duplicate `create_evidence_package_async()` calls causing duplicate evidence writes.

**Changes**: `pipeline.py` — removed duplicate call, added `_evidence_last_frame` cooldown + `_MAX_EVIDENCE_PER_FRAME=3` cap.

### Fix 3: Face Detection — Zero Faces (Phase E)
**Root cause**: YuNet score threshold 0.6 too high for surveillance faces. `best_face_in_box` ran YuNet on full 1920x1080 frame (5s each!) instead of person crops.

**Changes**: `evidence_detectors.py`:
- Lowered default threshold: 0.6→0.3
- Added crop-based detection: crops top 50% of person box, runs YuNet on crop, maps coordinates back
- Full-frame fallback with wider margin (8px→15px)
- Added character confusion pairs for OCR normalization (`plate_aggregator.py`)

| Metric | Before | After |
|---|---|---|
| Face detections (VIRAT RGB) | 0 | **58** in 30 frames |
| Detection approach | Full frame (5s) | Person crop (~50ms) |

### Fix 4: OCR Normalization (Phase C/D)
**Root cause**: PP-OCRv3 confuses 3↔E, 5↔S, 0↔O, 1↔I. Same plate read as different text, fragmenting consensus.

**Changes**: `plate_aggregator.py` — added `plate_texts_similar()` fuzzy grouping using character confusion pairs. Groups observations by confusable similarity instead of exact match.

### Fix 5: Silent Exception Logging (Phase H)
**Root cause**: YuNet and OCR failures logged at `debug` level, invisible in production.

**Changes**: `evidence_detectors.py` — promoted to `warning` level for YuNet and OCR inference failures.

---

## Performance Results (Phase I)

| Video | Resolution | Modality | FPS | Det (ms) | Track (ms) | Bottleneck |
|---|---|---|---|---|---|---|
| ANPR | 1920×1080 | STANDARD | 5.2 | 96.6 | 8.7 | Plate (178ms) |
| Night IR | 320×240 | IR_NIGHT | 10.9 | 86.1 | 4.2 | Det (86ms) |
| Thermal | 640×360 | THERMAL | 7.7 | 77.8 | 2.5 | Face (270ms) |
| PTB-TIR Park | 1280×720 | THERMAL | 3.9 | 95.0 | 4.9 | Face (1011ms) |
| NIRPed | 1280×720 | NIGHT_IR | 5.3 | 86.3 | 5.2 | Face (510ms) |

**Key insight**: Tracking is consistently fast (2-9ms). Detection is stable (78-97ms). Face detection on large person crops is the main bottleneck when persons are present.

---

## Modality Results

### Night/IR (Phase F)
- **Night IR (320×240)**: 0.7 dets/frame, 31 unique IDs — YOLO detects some objects but limited by low resolution + IR appearance
- **NIRPed (1280×720)**: 5.3 dets/frame, 28 unique IDs — real nighttime color NIR (850nm) works well
- **Face detection**: 0 faces on IR — YuNet is RGB-trained, expected limitation

### Thermal (Phase G)
- **Original thermal (640×360)**: 0.1 dets/frame — likely false-colored RGB, poor thermal contrast
- **PTB-TIR Park (1280×720)**: 9.0 dets/frame — genuine thermal IR, YOLO detects well
- **PTB-TIR Road (1280×720)**: 3.9 dets/frame — genuine thermal IR
- **Face detection**: 0 faces — YuNet is RGB-trained, expected

### ANPR (Phase C/D)
- **87 plate detections** in 30 frames (2.9 plates/frame)
- **87 OCR reads** (100% read rate)
- Plate crop sizes: 62-108px wide, 17-25px tall
- OCR output partially garbled at this resolution (expected for small plates)
- Temporal aggregation now groups confusable readings (3↔E, etc.)

---

## Regression Test (Phase J)

| Video | Status | FPS | Errors |
|---|---|---|---|
| ANPR (1920×1080) | PASS | 3.3 | 0 |
| Night IR (320×240) | PASS | 3.9 | 0 |
| Thermal (640×360) | PASS | 12.8 | 0 |
| PTB-TIR Park (1280×720) | PASS | 6.3 | 0 |
| PTB-TIR Road (1280×720) | PASS | 8.9 | 0 |
| NIRPed (1280×720) | PASS | 5.2 | 0 |
| VIRAT RGB (1920×1080) | PASS | 9.1 | 0 |

**ALL PASS — 7/7 videos, 0 errors**

---

## Files Modified

| File | Changes |
|---|---|
| `backend/tracking/bytetrack_wrapper.py` | NMS threshold 0.60→0.40, vehicle-pair 0.25, `deduplicate_tracks()` with zero-area guard |
| `backend/tracking/pipeline.py` | Evidence cap/cooldown, `evidence_count` increment fix |
| `backend/detection/evidence_detectors.py` | YuNet threshold 0.6→0.3, crop-based face detection, exception logging debug→warning |
| `backend/detection/plate_aggregator.py` | `plate_texts_similar()` fuzzy grouping, character confusion pairs |

## Test Data Added

| Path | Description |
|---|---|
| `dataset/surveillance/thermal_real/` | 5 PTB-TIR thermal MP4s (verified genuine thermal IR) |
| `dataset/surveillance/night_real/nirped_val_sequence.mp4` | 160-frame NIRPed nighttime color NIR video |
| `dataset/surveillance/night_real/nightowls_validation.json` | NightOwls annotations (51K images, 17K annotations) |

---

## Known Limitations

1. **Face detection**: YuNet is RGB-only — no face detection on night/IR or thermal footage
2. **ANPR at 1080p**: Plate crops (62-108px) are marginal for OCR; results partially garbled
3. **Detection on thermal**: YOLOv8n is RGB-trained; performance on genuine thermal is decent but not optimal
4. **Processing speed**: 3-10 FPS depending on resolution; real-time not guaranteed at 1080p
