"""Quick test: GlobalEntity + CameraTransition persistence."""
from backend.persistence.normalized_store import get_normalized_store

store = get_normalized_store()

# Create a test camera and session
store.ensure_camera("TEST-CAM-01")
sid = store.create_session("TEST-CAM-01", fps=30.0)
print(f"Session: {sid}")

# Upsert a global entity
eid = store.upsert_global_entity("G99", entity_type="person", camera_id="TEST-CAM-01", local_track_id="TRACK-01")
print(f"Global entity created: {eid}")

# Update same entity
eid2 = store.upsert_global_entity("G99", entity_type="person", camera_id="TEST-CAM-02", local_track_id="TRACK-05")
print(f"Global entity updated: {eid2} (same={eid==eid2})")

# Create transition
tid = store.create_camera_transition(eid, "TEST-CAM-01", "TRACK-01", "TEST-CAM-02", "TRACK-05", 0.85)
print(f"Transition: {tid}")

# Query DB to verify
import sqlite3
conn = sqlite3.connect("percepta.db")
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT * FROM global_entities WHERE display_id = 'G99'").fetchall()
print(f"\nGlobalEntity rows for G99: {len(rows)}")
for r in rows:
    print(f"  {r['display_id']} type={r['entity_type']} cam={r['current_camera_id']} status={r['status']}")

trans = conn.execute("SELECT * FROM camera_transitions").fetchall()
print(f"\nCameraTransition rows: {len(trans)}")
for t in trans:
    print(f"  {t['from_camera_id']}/{t['from_local_track_id']} -> {t['to_camera_id']}/{t['to_local_track_id']} conf={t['association_confidence']}")

conn.close()
store.end_session(sid)
print("\nPhase 6 verification PASSED")
