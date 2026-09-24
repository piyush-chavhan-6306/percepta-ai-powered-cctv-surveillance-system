"""Deep analysis of the track ID diagnostic data."""
import json
from collections import defaultdict

with open("scratch/track_id_diagnostic.json") as f:
    data = json.load(f)

frame_log = data["frame_log"]
all_frames = data.get("frame_log", [])

# Build complete frame history from the log
# We saved last 200 frames, let's also check id_switches and ping_pongs

print("=== TRACK ID LIFECYCLE ANALYSIS ===\n")

# For each track, show its complete lifecycle
id_history = defaultdict(list)
for fl in all_frames:
    for td in fl["track_details"]:
        tid = td["track_id"]
        id_history[tid].append({
            "frame": fl["frame"],
            "center": td["center"],
            "bbox": td["bbox"],
            "age": td["age"],
            "hits": td["hits"],
            "lifecycle": td["lifecycle"],
            "confidence": td["confidence"],
        })

# Find tracks that are very active (most sightings) and check their stability
print("Top 10 most-seen tracks:")
for tid, sightings in sorted(id_history.items(), key=lambda x: -len(x[1]))[:10]:
    frames = [s["frame"] for s in sightings]
    gaps = [frames[i+1] - frames[i] for i in range(len(frames)-1)]
    max_gap = max(gaps) if gaps else 0
    avg_conf = sum(s["confidence"] for s in sightings) / len(sightings)
    print(f"  ID #{tid}: {len(sightings)} frames, range {frames[0]}-{frames[-1]}, "
          f"max_gap={max_gap}, avg_conf={avg_conf:.3f}")
    
    # Show all gaps > 3
    big_gaps = [(i, frames[i], frames[i+1]) for i in range(len(frames)-1) if frames[i+1] - frames[i] > 3]
    if big_gaps:
        for idx, f_before, f_after in big_gaps:
            print(f"    GAP: frames {f_before} -> {f_after} ({f_after - f_before} frames)")

print("\n=== PING-PONG DETAILED ANALYSIS ===")
# Look at the specific ping-pong: ID #1 vs ID #5
# And also ID #24 which has a 26-frame gap
for target_id in ["1", "5", "24", "46"]:
    if target_id in id_history:
        sightings = id_history[target_id]
        frames = [s["frame"] for s in sightings]
        print(f"\n--- ID #{target_id} Lifecycle ---")
        # Show first and last 5 sightings
        for s in sightings[:5]:
            print(f"  Frame {s['frame']}: center=({s['center'][0]:.0f},{s['center'][1]:.0f}) "
                  f"conf={s['confidence']:.3f} age={s['age']} lifecycle={s['lifecycle']}")
        if len(sightings) > 10:
            print(f"  ... ({len(sightings) - 10} more) ...")
            for s in sightings[-5:]:
                print(f"  Frame {s['frame']}: center=({s['center'][0]:.0f},{s['center'][1]:.0f}) "
                      f"conf={s['confidence']:.3f} age={s['age']} lifecycle={s['lifecycle']}")

# Now look at the critical moment: what happens at the gap
print("\n=== FRAME-BY-FRAME AT GAP BOUNDARIES ===")
# ID #24 gap around frame 251 (it reappears later at 145-302 with gap 20)
# Actually ID #24: frames 4-251 with max_gap=26
if "24" in id_history:
    frames_24 = [s["frame"] for s in id_history["24"]]
    for i in range(len(frames_24)-1):
        if frames_24[i+1] - frames_24[i] > 10:
            gap_start = frames_24[i]
            gap_end = frames_24[i+1]
            print(f"\nID #24 GAP: frame {gap_start} -> frame {gap_end}")
            # Show what's happening around this gap
            for fl in all_frames:
                if gap_start - 5 <= fl["frame"] <= gap_end + 5:
                    ids_str = ",".join(fl["tracks_after"]) if fl["tracks_after"] else "none"
                    marker = ""
                    if fl["frame"] == gap_start:
                        marker = " <-- LAST SEEN BEFORE GAP"
                    elif fl["frame"] == gap_end:
                        marker = " <-- FIRST SEEN AFTER GAP"
                    print(f"  F{fl['frame']:4d}: tracks=[{ids_str}] "
                          f"dets={fl['detections_after_nms']} new={fl['new_ids']} lost={fl['lost_ids']}{marker}")

# Check if the duplicate suppression is working
print("\n=== DUPLICATE SUPPRESSION EFFECTIVENESS ===")
total_raw = sum(fl["detections_raw"] for fl in all_frames)
total_filtered = sum(fl["detections_after_nms"] for fl in all_frames)
print(f"Total raw detections: {total_raw}")
print(f"After NMS: {total_filtered}")
print(f"Suppressed: {total_raw - total_filtered} ({(total_raw-total_filtered)/max(total_raw,1)*100:.1f}%)")

# Check for objects with multiple simultaneous IDs
print("\n=== MULTIPLE IDs ON SAME OBJECT ===")
multi_id_frames = 0
for fl in all_frames:
    if len(fl["track_details"]) >= 2:
        centers = [(td["track_id"], td["center"]) for td in fl["track_details"]]
        for i in range(len(centers)):
            for j in range(i+1, len(centers)):
                dist = ((centers[i][1][0] - centers[j][1][0])**2 + 
                        (centers[i][1][1] - centers[j][1][1])**2)**0.5
                if dist < 30:  # Very close = likely same object
                    multi_id_frames += 1
                    if multi_id_frames <= 5:
                        print(f"  Frame {fl['frame']}: ID #{centers[i][0]} and ID #{centers[j][0]} "
                              f"at dist={dist:.1f}px")
                    break
print(f"Total frames with multiple IDs on same object (<30px): {multi_id_frames}")

# Track creation rate
print("\n=== TRACK CREATION/DESTRUCTION RATE ===")
total_created = sum(len(fl["new_ids"]) for fl in all_frames)
total_lost = sum(len(fl["lost_ids"]) for fl in all_frames)
print(f"Total new tracks created: {total_created}")
print(f"Total tracks lost: {total_lost}")
print(f"Average tracks per frame: {sum(len(fl['tracks_after']) for fl in all_frames)/len(all_frames):.1f}")
print(f"Track churn rate: {total_created/len(all_frames):.2f} new tracks/frame")
