"""
Phase 3: Post-migration verification
"""
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(r"D:\SIH   border cctv\percepta.db")
conn = sqlite3.connect(str(DB_PATH))
conn.row_factory = sqlite3.Row

SEP = "=" * 70
print(SEP)
print("POST-MIGRATION VERIFICATION")
print(SEP)

# 1. Row counts
print("\n--- 1. ROW COUNTS ---")
src = conn.execute("SELECT COUNT(*) FROM event_logs").fetchone()[0]
dst = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
print(f"  event_logs (source): {src}")
print(f"  events (target):     {dst}")
print(f"  Match: {src == dst}")

# 2. Per-type breakdown
print("\n--- 2. PER-TYPE BREAKDOWN ---")
for etype in ["ZONE", "ALERT", "DETECTION"]:
    s = conn.execute("SELECT COUNT(*) FROM event_logs WHERE event_type = ?", (etype,)).fetchone()[0]
    d = conn.execute("SELECT COUNT(*) FROM events WHERE event_type = ?", (etype,)).fetchone()[0]
    print(f"  {etype}: source={s} target={d} match={s == d}")

# 3. Event ID uniqueness
print("\n--- 3. EVENT ID UNIQUENESS ---")
dupes = conn.execute("SELECT COUNT(*) FROM (SELECT event_id FROM events GROUP BY event_id HAVING COUNT(*) > 1)").fetchone()[0]
print(f"  Duplicate event_ids: {dupes}")

# 4. PK coverage
print("\n--- 4. PK COVERAGE ---")
src_ids = set(r[0] for r in conn.execute("SELECT event_id FROM event_logs").fetchall())
dst_ids = set(r[0] for r in conn.execute("SELECT event_id FROM events").fetchall())
print(f"  Source IDs: {len(src_ids)}")
print(f"  Target IDs: {len(dst_ids)}")
print(f"  Source subset of Target: {src_ids.issubset(dst_ids)}")
print(f"  Target subset of Source: {dst_ids.issubset(src_ids)}")

# 5. Timestamp preservation (spot check)
print("\n--- 5. TIMESTAMP PRESERVATION (sample 10) ---")
sample = conn.execute("""
    SELECT e.event_id, e.timestamp as e_ts, l.timestamp as l_ts,
           e.event_type, e.camera_id
    FROM events e
    JOIN event_logs l ON e.event_id = l.event_id
    ORDER BY RANDOM() LIMIT 10
""").fetchall()
mismatches = 0
for r in sample:
    match = r['e_ts'] == r['l_ts']
    if not match:
        mismatches += 1
        print(f"  MISMATCH: {r['event_id']} {r['event_type']} {r['camera_id']}")
        print(f"    events:  {r['e_ts']}")
        print(f"    logs:    {r['l_ts']}")
print(f"  Timestamp mismatches: {mismatches}/10")

# 6. Confidence preservation
print("\n--- 6. CONFIDENCE PRESERVATION ---")
conf_match = conn.execute("""
    SELECT COUNT(*) FROM events e
    JOIN event_logs l ON e.event_id = l.event_id
    WHERE (e.confidence = l.confidence) OR (e.confidence IS NULL AND l.confidence IS NULL)
""").fetchone()[0]
print(f"  Confidence matches: {conf_match}/{dst}")

# 7. Source preservation
print("\n--- 7. SOURCE PRESERVATION ---")
src_match = conn.execute("""
    SELECT COUNT(*) FROM events e
    JOIN event_logs l ON e.event_id = l.event_id
    WHERE e.source = l.source
""").fetchone()[0]
print(f"  Source matches: {src_match}/{dst}")

# 8. Metadata integrity (sample payloads)
print("\n--- 8. METADATA INTEGRITY (sample 5) ---")
sample = conn.execute("SELECT event_id, event_type, metadata FROM events ORDER BY RANDOM() LIMIT 5").fetchall()
for r in sample:
    try:
        meta = json.loads(r['metadata']) if r['metadata'] else None
        keys = list(meta.keys()) if meta else []
        print(f"  {r['event_id'][:8]}... [{r['event_type']}] keys={len(keys)}: {keys[:5]}...")
    except Exception as ex:
        print(f"  {r['event_id'][:8]}... [{r['event_type']}] PARSE ERROR: {ex}")

# 9. FK integrity (no FK violations)
print("\n--- 9. FK INTEGRITY ---")
null_session = conn.execute("SELECT COUNT(*) FROM events WHERE session_id IS NOT NULL").fetchone()[0]
null_global = conn.execute("SELECT COUNT(*) FROM events WHERE global_entity_id IS NOT NULL").fetchone()[0]
null_zone = conn.execute("SELECT COUNT(*) FROM events WHERE zone_id IS NOT NULL").fetchone()[0]
null_incident = conn.execute("SELECT COUNT(*) FROM events WHERE incident_id IS NOT NULL").fetchone()[0]
print(f"  Non-null session_id: {null_session} (should be 0)")
print(f"  Non-null global_entity_id: {null_global} (should be 0)")
print(f"  Non-null zone_id: {null_zone} (should be 0)")
print(f"  Non-null incident_id: {null_incident} (should be 0)")

# 10. Database size
print("\n--- 10. DATABASE SIZE ---")
size = DB_PATH.stat().st_size
print(f"  Database size: {size / 1024 / 1024:.1f} MB")

conn.close()
print(f"\n{SEP}")
print("VERIFICATION COMPLETE")
print(SEP)
