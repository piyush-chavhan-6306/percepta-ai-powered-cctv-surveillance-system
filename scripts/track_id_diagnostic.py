"""
TRACK ID INSTABILITY DIAGNOSTIC
Traces complete detection -> tracking -> ID lifecycle on real VIRAT footage.
Records every relevant frame to find the EXACT root cause of ID switching.
"""
import sys, os, json, time, logging
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2
import numpy as np

from backend.detection.detector import ObjectDetector, get_detector
from backend.tracking.bytetrack_wrapper import ByteTrackTracker, suppress_duplicate_detections
from backend.ingestion.adapter import FrameData
from backend.events.schema import SourceType

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("track_diag")
logger.setLevel(logging.INFO)

VIDEO = "dataset/surveillance/anpr_vehicle_checkpoint.mp4"
OUTPUT = "scratch/track_id_diagnostic.json"

def run_diagnostic():
    cap = cv2.VideoCapture(VIDEO)
    if not cap.isOpened():
        print(f"ERROR: Cannot open {VIDEO}")
        return

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"Video: {VIDEO} ({w}x{h}, {fps} FPS, {total_frames} frames)")

    detector = get_detector()
    detector.initialize()
    tracker = ByteTrackTracker()
    tracker.initialize()

    frame_log = []
    id_history = defaultdict(list)  # track_id -> list of frame_numbers
    all_ids_seen = set()
    detection_id_counter = 0

    frame_num = 0
    t_start = time.time()

    while True:
        ret, frame_bgr = cap.read()
        if not ret:
            break

        frame_num += 1
        timestamp = frame_num / fps if fps > 0 else time.time()

        frame_data = FrameData(
            camera_id="diag_001",
            image=frame_bgr,
            frame_number=frame_num,
            fps=fps,
            width=w,
            height=h,
            timestamp=datetime_obj(timestamp),
            source=SourceType.VIDEO_FILE,
        )

        # 1. Detect
        t0 = time.perf_counter()
        detections = detector.detect(frame_bgr)
        t_det = (time.perf_counter() - t0) * 1000

        # 1b. Cross-class NMS
        pre_nms_count = len(detections) if detections else 0
        filtered_dets = suppress_duplicate_detections(detections) if detections else []
        post_nms_count = len(filtered_dets)

        # 2. Track
        tracks_before = {str(t.track_id): t.track_id for t in tracker.get_active_tracks()}
        t0 = time.perf_counter()
        tracks = tracker.update(detections, frame_data)
        t_track = (time.perf_counter() - t0) * 1000

        tracks_after = {}
        track_details = []
        for t in tracks:
            tid = str(t.track_id)
            tracks_after[tid] = t.track_id
            all_ids_seen.add(tid)
            id_history[tid].append(frame_num)
            track_details.append({
                "track_id": tid,
                "class": t.object_class,
                "confidence": round(t.confidence, 4),
                "bbox": [round(v, 1) for v in t.bounding_box],
                "center": [t.center_x, t.center_y],
                "age": t.age,
                "hits": t.hits,
                "time_since_update": t.time_since_update,
                "lifecycle": t.lifecycle,
                "provenance": t.provenance,
            })

        # Detection details for this frame
        det_details = []
        for d in (filtered_dets or []):
            det_details.append({
                "class": d.class_name,
                "class_id": d.class_id,
                "confidence": round(d.confidence, 4),
                "bbox": [round(v, 1) for v in d.bounding_box],
            })

        # Track ID changes
        new_ids = set(tracks_after.keys()) - set(tracks_before.keys())
        lost_ids = set(tracks_before.keys()) - set(tracks_after.keys())
        kept_ids = set(tracks_after.keys()) & set(tracks_before.keys())

        frame_log.append({
            "frame": frame_num,
            "timestamp": round(timestamp, 3),
            "detections_raw": pre_nms_count,
            "detections_after_nms": post_nms_count,
            "detection_details": det_details,
            "tracks_before": list(tracks_before.keys()),
            "tracks_after": list(tracks_after.keys()),
            "new_ids": list(new_ids),
            "lost_ids": list(lost_ids),
            "kept_ids": list(kept_ids),
            "track_details": track_details,
            "det_ms": round(t_det, 1),
            "track_ms": round(t_track, 1),
        })

        if frame_num % 100 == 0:
            elapsed = time.time() - t_start
            fps_actual = frame_num / elapsed if elapsed > 0 else 0
            print(f"  Frame {frame_num}/{total_frames} ({fps_actual:.1f} fps) "
                  f"dets={post_nms_count} tracks={len(tracks)} "
                  f"new={len(new_ids)} lost={len(lost_ids)} total_ids={len(all_ids_seen)}")

    cap.release()
    elapsed = time.time() - t_start
    print(f"\nDone: {frame_num} frames in {elapsed:.1f}s ({frame_num/elapsed:.1f} fps)")

    # ANALYSIS: Find ID switches
    print(f"\nTotal unique track IDs: {len(all_ids_seen)}")
    print(f"Total frames: {frame_num}")

    # Find tracks that appear, disappear, and reappear (ID switches)
    id_switches = []
    for tid, frames in id_history.items():
        if len(frames) < 2:
            continue
        gaps = []
        for i in range(1, len(frames)):
            gap = frames[i] - frames[i-1]
            gaps.append(gap)
        max_gap = max(gaps) if gaps else 0
        if max_gap > 5:
            id_switches.append({
                "track_id": tid,
                "appearances": len(frames),
                "first_frame": frames[0],
                "last_frame": frames[-1],
                "max_gap": max_gap,
                "all_frames": frames,
            })

    print(f"\nTracks with gaps > 5 frames (potential ID switches): {len(id_switches)}")
    for sw in sorted(id_switches, key=lambda x: -x["max_gap"])[:10]:
        print(f"  ID #{sw['track_id']}: {sw['appearances']} sightings, "
              f"frames {sw['first_frame']}-{sw['last_frame']}, max_gap={sw['max_gap']}")

    # Detect actual ping-pong patterns: ID A appears, disappears, then same physical object gets ID B, then B disappears and A reappears
    print("\n--- Searching for ID ping-pong patterns ---")
    # For each pair of tracks, check if their active frames interleave
    all_track_ids = sorted(all_ids_seen, key=lambda x: int(x) if x.isdigit() else 0)
    ping_pongs = []
    for i in range(len(all_track_ids)):
        for j in range(i+1, len(all_track_ids)):
            tid_a = all_track_ids[i]
            tid_b = all_track_ids[j]
            frames_a = set(id_history[tid_a])
            frames_b = set(id_history[tid_b])
            # Check if they overlap in time (active in the same ~30 frame window)
            if not frames_a or not frames_b:
                continue
            # Check proximity: are they both active within a 60-frame window?
            for fa in frames_a:
                near_b = [fb for fb in frames_b if abs(fb - fa) < 30]
                if near_b:
                    # Check spatial proximity: are their boxes near each other?
                    for la in frame_log:
                        if la["frame"] == fa:
                            for td in la["track_details"]:
                                if td["track_id"] == tid_a:
                                    box_a = td["bbox"]
                                    center_a = td["center"]
                                    for fb in near_b[:1]:
                                        for lb in frame_log:
                                            if lb["frame"] == fb:
                                                for td2 in lb["track_details"]:
                                                    if td2["track_id"] == tid_b:
                                                        box_b = td2["bbox"]
                                                        center_b = td2["center"]
                                                        dist = ((center_a[0]-center_b[0])**2 + (center_a[1]-center_b[1])**2)**0.5
                                                        if dist < 100:
                                                            ping_pongs.append({
                                                                "id_a": tid_a,
                                                                "id_b": tid_b,
                                                                "frame_a": fa,
                                                                "frame_b": fb,
                                                                "distance": round(dist, 1),
                                                                "center_a": center_a,
                                                                "center_b": center_b,
                                                            })
                                    break
                        if len(ping_pongs) > 50:
                            break
                if len(ping_pongs) > 50:
                    break
            if len(ping_pongs) > 50:
                break

    print(f"Ping-pong candidates (spatially close, temporally interleaved): {len(ping_pongs)}")
    for pp in ping_pongs[:10]:
        print(f"  ID #{pp['id_a']} (frame {pp['frame_a']}) <-> ID #{pp['id_b']} (frame {pp['frame_b']}), "
              f"dist={pp['distance']:.0f}px")

    # Save full log
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w") as f:
        json.dump({
            "video": VIDEO,
            "resolution": f"{w}x{h}",
            "fps": fps,
            "total_frames": frame_num,
            "total_unique_ids": len(all_ids_seen),
            "id_switches": id_switches,
            "ping_pongs": ping_pongs,
            "frame_log": frame_log[-200:],  # last 200 frames for inspection
        }, f, indent=2, default=str)
    print(f"\nFull log saved to {OUTPUT}")

    # Show the most problematic frames
    if ping_pongs:
        print("\n=== DETAILED INSPECTION OF FIRST PING-PONG ===")
        pp = ping_pongs[0]
        target_frames = range(max(1, pp["frame_a"] - 15), min(frame_num, pp["frame_b"] + 15))
        for fl in frame_log:
            if fl["frame"] in target_frames:
                ids_str = ",".join(fl["tracks_after"]) if fl["tracks_after"] else "none"
                marker = ""
                if fl["frame"] == pp["frame_a"]:
                    marker = f" <-- ID #{pp['id_a']} ACTIVE"
                elif fl["frame"] == pp["frame_b"]:
                    marker = f" <-- ID #{pp['id_b']} ACTIVE"
                print(f"  F{fl['frame']:4d}: dets={fl['detections_after_nms']:2d} "
                      f"tracks=[{ids_str}] new={fl['new_ids']} lost={fl['lost_ids']}{marker}")


def datetime_obj(ts):
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ts, tz=timezone.utc)


if __name__ == "__main__":
    run_diagnostic()
