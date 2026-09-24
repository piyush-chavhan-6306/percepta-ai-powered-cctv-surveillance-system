"""Deep dive into the ID #24 gap and multi-ID duplication."""
import json
from collections import defaultdict

with open("scratch/track_id_diagnostic.json") as f:
    data = json.load(f)

# Load ALL frame data (we only saved last 200, but let's work with what we have)
frame_log = data["frame_log"]

# Rebuild ID history
id_history = defaultdict(list)
for fl in frame_log:
    for td in fl["track_details"]:
        tid = td["track_id"]
        id_history[tid].append({
            "frame": fl["frame"],
            "center": td["center"],
            "bbox": td["bbox"],
        })

# ID #24: was at center ~(521, 322) before gap, check if it reappears at same spot
print("=== ID #24 GAP ANALYSIS ===")
frames_24 = id_history.get("24", [])
print(f"ID #24 total sightings: {len(frames_24)}")
if frames_24:
    # Find positions before and after the gap
    for s in frames_24[:5]:
        print(f"  Before: Frame {s['frame']}: center=({s['center'][0]:.0f},{s['center'][1]:.0f})")
    for s in frames_24[-5:]:
        print(f"  After:  Frame {s['frame']}: center=({s['center'][0]:.0f},{s['center'][1]:.0f})")

# Check what NEW tracks appear near ID #24's position (521, 322) right after the gap
print("\n=== WHAT APPEARS AT ID #24'S POSITION AFTER GAP? ===")
for fl in frame_log:
    if 136 <= fl["frame"] <= 160:
        for td in fl["track_details"]:
            center = td["center"]
            dist = ((center[0] - 521)**2 + (center[1] - 322)**2)**0.5
            if dist < 50:
                marker = " <-- NEW" if td["track_id"] not in [s["frame"] for s in []] else ""
                print(f"  Frame {fl['frame']}: ID #{td['track_id']} at ({center[0]:.0f},{center[1]:.0f}) "
                      f"dist={dist:.0f} conf={td['confidence']:.3f} lifecycle={td['lifecycle']}{marker}")

# Analyze the multi-ID duplication more carefully
print("\n=== MULTI-ID DUPLICATION ANALYSIS ===")
# Group tracks by spatial proximity in each frame
dup_count = 0
dup_examples = []
for fl in frame_log:
    centers = [(td["track_id"], td["center"], td["bbox"]) for td in fl["track_details"]]
    for i in range(len(centers)):
        for j in range(i+1, len(centers)):
            dist = ((centers[i][1][0] - centers[j][1][0])**2 + 
                    (centers[i][1][1] - centers[j][1][1])**2)**0.5
            if dist < 30:
                dup_count += 1
                if len(dup_examples) < 10:
                    dup_examples.append({
                        "frame": fl["frame"],
                        "id_a": centers[i][0],
                        "id_b": centers[j][0],
                        "dist": round(dist, 1),
                        "center_a": centers[i][1],
                        "center_b": centers[j][1],
                    })

print(f"Total duplicate instances (dist < 30px): {dup_count}")
for ex in dup_examples:
    print(f"  Frame {ex['frame']}: ID #{ex['id_a']} and #{ex['id_b']} at {ex['dist']:.0f}px apart")

# Check the FIRST 103 frames (before the log window)
# ID #24 first appears at frame 4, and we have data from frame 103
# The gap 135->156 means 21 frames missing
print("\n=== KEY INSIGHT: What's happening with ID #24? ===")
print("ID #24 first seen at frame 4, position ~(526,324)")
print("ID #24 disappears at frame 136, reappears at frame 156")
print("Position stays at ~(521,322) throughout — it's a STATIC object (same position)")
print()
print("This is NOT a ping-pong (ID A->B->A).")
print("This is a TRACK DROPOUT: the detector momentarily misses the object,")
print("and when it reappears, ByteTrack re-creates the track with the SAME ID")
print("(via re_activate in the lost pool) or the spatial reassociation kicks in.")
print()
print("The REAL problem is different:")
print("  - 69 unique IDs for ~22 objects = 3x overcounting")
print("  - 516 frames with multiple IDs on same object")
print("  - Objects get duplicate IDs because the cross-class NMS isn't aggressive enough")

# Count unique IDs per frame
print("\n=== IDs PER FRAME ===")
for fl in frame_log[:5]:
    print(f"Frame {fl['frame']}: {len(fl['tracks_after'])} tracks, {fl['detections_after_nms']} detections")
    # Show which IDs are very close to each other
    centers = [(td["track_id"], td["center"]) for td in fl["track_details"]]
    close_pairs = []
    for i in range(len(centers)):
        for j in range(i+1, len(centers)):
            dist = ((centers[i][1][0] - centers[j][1][0])**2 + 
                    (centers[i][1][1] - centers[j][1][1])**2)**0.5
            if dist < 50:
                close_pairs.append((centers[i][0], centers[j][0], dist))
    if close_pairs:
        for a, b, d in close_pairs:
            print(f"  Close: ID #{a} <-> ID #{b} at {d:.0f}px")
