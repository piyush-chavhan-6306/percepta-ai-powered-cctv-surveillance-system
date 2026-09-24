"""
Phase 3: Full Legacy event_logs Data Audit (corrected schema)
"""
import json
import sqlite3
from collections import Counter
from pathlib import Path

DB_PATH = Path(r"D:\SIH   border cctv\percepta.db")
conn = sqlite3.connect(str(DB_PATH))
conn.row_factory = sqlite3.Row

SEP = "=" * 70
print(SEP)
print("LEGACY EVENT_LOGS FULL AUDIT")
print(SEP)

# 1. Schema
print("\n--- 1. SCHEMA ---")
cols = conn.execute("PRAGMA table_info(event_logs)").fetchall()
for c in cols:
    print(f"  {c['name']:<20} {c['type']:<20} {'NOT NULL' if c['notnull'] else 'NULLABLE':<10} {'PK' if c['pk'] else ''}")

# 2. Row count
print("\n--- 2. ROW COUNT ---")
total = conn.execute("SELECT COUNT(*) FROM event_logs").fetchone()[0]
print(f"  Total rows: {total}")

# 3. Date/time range
print("\n--- 3. DATE/TIME RANGE ---")
min_ts = conn.execute("SELECT MIN(timestamp) FROM event_logs").fetchone()[0]
max_ts = conn.execute("SELECT MAX(timestamp) FROM event_logs").fetchone()[0]
print(f"  Min timestamp: {min_ts}")
print(f"  Max timestamp: {max_ts}")

# 4. Distinct event_type values
print("\n--- 4. DISTINCT EVENT_TYPE VALUES ---")
rows = conn.execute("SELECT event_type, COUNT(*) as cnt FROM event_logs GROUP BY event_type ORDER BY cnt DESC").fetchall()
for r in rows:
    print(f"  {r['event_type']:<40} {r['cnt']:>6}")

# 5. Distinct source values
print("\n--- 5. DISTINCT SOURCE VALUES ---")
rows = conn.execute("SELECT source, COUNT(*) as cnt FROM event_logs GROUP BY source ORDER BY cnt DESC").fetchall()
for r in rows:
    print(f"  {str(r['source']):<40} {r['cnt']:>6}")

# 6. NULL/empty field counts
print("\n--- 6. NULL/EMPTY FIELD COUNTS ---")
for c in cols:
    cname = c['name']
    null_cnt = conn.execute(f"SELECT COUNT(*) FROM event_logs WHERE {cname} IS NULL").fetchone()[0]
    empty_cnt = conn.execute(f"SELECT COUNT(*) FROM event_logs WHERE {cname} = ''").fetchone()[0]
    if null_cnt > 0 or empty_cnt > 0:
        print(f"  {cname:<20} NULL={null_cnt:>6}  EMPTY={empty_cnt:>6}")

# 7. Distinct camera_id values
print("\n--- 7. DISTINCT CAMERA_ID VALUES ---")
rows = conn.execute("SELECT camera_id, COUNT(*) as cnt FROM event_logs GROUP BY camera_id ORDER BY cnt DESC").fetchall()
for r in rows:
    print(f"  {str(r['camera_id']):<40} {r['cnt']:>6}")

# 8. JSON payload structure per event_type
print("\n--- 8. JSON PAYLOAD STRUCTURE PER EVENT_TYPE ---")
for etype in ['ZONE', 'ALERT', 'DETECTION']:
    rows = conn.execute("SELECT payload FROM event_logs WHERE event_type = ? AND payload IS NOT NULL LIMIT 200", (etype,)).fetchall()
    all_keys = Counter()
    json_errors = 0
    samples = []
    for r in rows:
        try:
            d = json.loads(r['payload'])
            all_keys.update(d.keys())
            if len(samples) < 2:
                samples.append(d)
        except (json.JSONDecodeError, TypeError):
            json_errors += 1
    print(f"\n  [{etype}] sampled={len(rows)}, json_errors={json_errors}")
    print(f"  Top payload keys:")
    for k, v in all_keys.most_common(15):
        print(f"    {k:<40} {v:>6}")
    if samples:
        print(f"  Sample payloads:")
        for s in samples:
            print(f"    {json.dumps(s, default=str)[:200]}")

# 9. Confidence distribution
print("\n--- 9. CONFIDENCE DISTRIBUTION ---")
rows = conn.execute("""
    SELECT
        CASE
            WHEN confidence IS NULL THEN 'NULL'
            WHEN confidence < 0.1 THEN '<0.1'
            WHEN confidence < 0.3 THEN '0.1-0.3'
            WHEN confidence < 0.5 THEN '0.3-0.5'
            WHEN confidence < 0.7 THEN '0.5-0.7'
            WHEN confidence < 0.9 THEN '0.7-0.9'
            ELSE '>=0.9'
        END as bucket,
        COUNT(*) as cnt
    FROM event_logs
    GROUP BY bucket
    ORDER BY cnt DESC
""").fetchall()
for r in rows:
    print(f"  {r['bucket']:<20} {r['cnt']:>6}")

# 10. track_id patterns
print("\n--- 10. TRACK_ID PATTERNS ---")
null_tid = conn.execute("SELECT COUNT(*) FROM event_logs WHERE track_id IS NULL").fetchone()[0]
empty_tid = conn.execute("SELECT COUNT(*) FROM event_logs WHERE track_id = ''").fetchone()[0]
has_tid = conn.execute("SELECT COUNT(*) FROM event_logs WHERE track_id IS NOT NULL AND track_id != ''").fetchone()[0]
print(f"  NULL track_id: {null_tid}")
print(f"  Empty track_id: {empty_tid}")
print(f"  Has track_id: {has_tid}")

# 11. incident_id patterns
print("\n--- 11. INCIDENT_ID PATTERNS ---")
null_iid = conn.execute("SELECT COUNT(*) FROM event_logs WHERE incident_id IS NULL").fetchone()[0]
empty_iid = conn.execute("SELECT COUNT(*) FROM event_logs WHERE incident_id = ''").fetchone()[0]
has_iid = conn.execute("SELECT COUNT(*) FROM event_logs WHERE incident_id IS NOT NULL AND incident_id != ''").fetchone()[0]
print(f"  NULL incident_id: {null_iid}")
print(f"  Empty incident_id: {empty_iid}")
print(f"  Has incident_id: {has_iid}")

# 12. Record ID uniqueness
print("\n--- 12. RECORD ID UNIQUENESS ---")
dupes = conn.execute("SELECT COUNT(*) FROM (SELECT event_id FROM event_logs GROUP BY event_id HAVING COUNT(*) > 1)").fetchone()[0]
print(f"  Duplicate event_ids: {dupes}")

# 13. Sample records from each event_type
print("\n--- 13. SAMPLE RECORDS (one per event_type) ---")
etypes = conn.execute("SELECT DISTINCT event_type FROM event_logs ORDER BY event_type").fetchall()
for et in etypes:
    row = conn.execute("SELECT * FROM event_logs WHERE event_type = ? LIMIT 1", (et['event_type'],)).fetchone()
    if row:
        print(f"\n  [{row['event_type']}]")
        for c in cols:
            val = row[c['name']]
            if val is not None and val != '':
                display = str(val)[:150]
                print(f"    {c['name']}: {display}")

# 14. Timestamp format analysis
print("\n--- 14. TIMESTAMP FORMAT ANALYSIS ---")
samples = conn.execute("SELECT DISTINCT substr(timestamp, 1, 10) as date_part, COUNT(*) as cnt FROM event_logs GROUP BY date_part ORDER BY cnt DESC LIMIT 10").fetchall()
print("  Top date prefixes:")
for r in samples:
    print(f"    {r['date_part']}: {r['cnt']} rows")

# 15. seq_id patterns
print("\n--- 15. SEQ_ID PATTERNS ---")
min_seq = conn.execute("SELECT MIN(seq_id) FROM event_logs").fetchone()[0]
max_seq = conn.execute("SELECT MAX(seq_id) FROM event_logs").fetchone()[0]
null_seq = conn.execute("SELECT COUNT(*) FROM event_logs WHERE seq_id IS NULL").fetchone()[0]
print(f"  seq_id range: {min_seq} -- {max_seq}")
print(f"  NULL seq_id: {null_seq}")

# 16. payload not-null check
print("\n--- 16. PAYLOAD INTEGRITY ---")
null_payload = conn.execute("SELECT COUNT(*) FROM event_logs WHERE payload IS NULL").fetchone()[0]
empty_payload = conn.execute("SELECT COUNT(*) FROM event_logs WHERE payload = ''").fetchone()[0]
valid_json = conn.execute("SELECT COUNT(*) FROM event_logs WHERE payload IS NOT NULL AND payload != '' AND json_valid(payload)").fetchone()[0]
print(f"  NULL payload: {null_payload}")
print(f"  Empty payload: {empty_payload}")
print(f"  Valid JSON payload: {valid_json}")

conn.close()
print(f"\n{SEP}")
print("AUDIT COMPLETE")
print(SEP)
