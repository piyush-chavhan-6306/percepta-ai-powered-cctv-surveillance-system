"""
Phase 3: Legacy event_logs → normalized events Migration
=========================================================

Strategy:
- Read all 36,432 rows from event_logs
- Map to normalized events schema
- Insert in controlled batches of 1,000
- Idempotent: uses legacy event_id as PK, skips existing
- Supports --dry-run, --batch-size, --limit flags
- Produces detailed migration report

Mapping:
  ZONE   (29,539) → events: payload→metadata, track_id→local_track_id
  ALERT  (6,891)  → events: payload→metadata, threat data preserved
  DETECTION (2)   → events: payload→metadata, bbox preserved

NOT created (insufficient data):
  - incidents (event ≠ incident)
  - alerts (event ≠ alert)
  - global_entity_id (no cross-camera data)
  - session_id (no session tracking in legacy)
  - zone_id FK (zones may not exist)
"""
import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

DB_PATH = Path(r"D:\SIH   border cctv\percepta.db")

# ── Schema for normalized events table ─────────────────────────────
# Matches backend/database/schema.py Event model exactly
EVENTS_COLUMNS = [
    "event_id",           # VARCHAR(36) PK — reuse legacy event_id
    "event_type",         # VARCHAR(64)
    "timestamp",          # DATETIME
    "camera_id",          # VARCHAR(64)
    "session_id",         # VARCHAR(36) nullable — NULL for legacy
    "local_track_id",     # VARCHAR(64) nullable — from legacy track_id
    "global_entity_id",   # VARCHAR(36) nullable — NULL (no cross-camera)
    "zone_id",            # VARCHAR(36) nullable — NULL (no FK)
    "incident_id",        # VARCHAR(36) nullable — NULL (no incidents)
    "entity_type",        # VARCHAR(32) nullable — inferred from event_type
    "confidence",         # FLOAT nullable
    "source",             # VARCHAR(32)
    "metadata",           # JSON nullable — full legacy payload
    "evidence_id",        # VARCHAR(36) nullable — NULL
]


def ensure_events_table(conn: sqlite3.Connection) -> bool:
    """Verify normalized events table exists. Create if not."""
    table_exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='events'"
    ).fetchone()
    if not table_exists:
        print("Creating normalized events table...")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id VARCHAR(36) PRIMARY KEY,
                event_type VARCHAR(64) NOT NULL,
                timestamp DATETIME NOT NULL,
                camera_id VARCHAR(64) NOT NULL,
                session_id VARCHAR(36),
                local_track_id VARCHAR(64),
                global_entity_id VARCHAR(36),
                zone_id VARCHAR(36),
                incident_id VARCHAR(36),
                entity_type VARCHAR(32),
                confidence FLOAT,
                source VARCHAR(32) NOT NULL DEFAULT 'pipeline',
                metadata JSON,
                evidence_id VARCHAR(36)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_event_cam_time ON events (camera_id, timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_event_type_time ON events (event_type, timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_event_incident ON events (incident_id, timestamp)")
        conn.commit()
        print("Events table created with indexes.")
        return True
    return False


def map_legacy_to_event(row: sqlite3.Row) -> dict | None:
    """
    Map a single legacy event_logs row to normalized events fields.
    Returns dict of column values, or None if row should be skipped.
    """
    event_id = row["event_id"]
    event_type = row["event_type"]
    timestamp = row["timestamp"]
    camera_id = row["camera_id"]
    track_id = row["track_id"]
    confidence = row["confidence"]
    source = row["source"]

    # Parse payload JSON
    payload_str = row["payload"]
    try:
        payload = json.loads(payload_str) if payload_str else {}
    except (json.JSONDecodeError, TypeError):
        payload = {}

    # Determine entity_type from event_type
    entity_type = None
    if event_type == "ZONE":
        entity_type = "person"  # ZONE events are person-related by default
    elif event_type == "ALERT":
        entity_type = "person"
    elif event_type == "DETECTION":
        # Extract from payload if available
        entity_type = payload.get("object_class", "person")

    return {
        "event_id": event_id,
        "event_type": event_type,
        "timestamp": timestamp,
        "camera_id": camera_id,
        "session_id": None,           # No session tracking in legacy
        "local_track_id": str(track_id) if track_id else None,
        "global_entity_id": None,     # No cross-camera data
        "zone_id": None,              # No FK to zones table
        "incident_id": None,          # No incidents in legacy
        "entity_type": entity_type,
        "confidence": confidence,
        "source": source,
        "metadata": payload_str,      # Full legacy payload preserved
        "evidence_id": None,          # No evidence in legacy
    }


def migration_batch(
    conn: sqlite3.Connection,
    offset: int,
    batch_size: int,
    dry_run: bool = False,
) -> tuple[int, int, int]:
    """
    Migrate one batch of legacy rows.
    Returns (inserted, skipped_existing, skipped_invalid).
    """
    rows = conn.execute(
        "SELECT * FROM event_logs ORDER BY seq_id LIMIT ? OFFSET ?",
        (batch_size, offset)
    ).fetchall()

    if not rows:
        return 0, 0, 0

    inserted = 0
    skipped_existing = 0
    skipped_invalid = 0

    for row in rows:
        event = map_legacy_to_event(row)
        if event is None:
            skipped_invalid += 1
            continue

        # Check idempotency: skip if event_id already exists
        exists = conn.execute(
            "SELECT 1 FROM events WHERE event_id = ?", (event["event_id"],)
        ).fetchone()
        if exists:
            skipped_existing += 1
            continue

        if not dry_run:
            placeholders = ", ".join(["?"] * len(EVENTS_COLUMNS))
            col_names = ", ".join(EVENTS_COLUMNS)
            values = [event[col] for col in EVENTS_COLUMNS]
            conn.execute(f"INSERT INTO events ({col_names}) VALUES ({placeholders})", values)

        inserted += 1

    if not dry_run:
        conn.commit()

    return inserted, skipped_existing, skipped_invalid


def run_migration(dry_run: bool = False, batch_size: int = 1000, limit: int | None = None):
    """Execute the full migration with reporting."""
    print("=" * 70)
    print(f"PHASE 3 MIGRATION: event_logs -> events {'(DRY RUN)' if dry_run else ''}")
    print("=" * 70)

    # Backup database first
    backup_path = DB_PATH.parent / f"{DB_PATH.stem}.backup_pre_phase3_{int(time.time())}{DB_PATH.suffix}"
    print(f"\nBacking up database to {backup_path.name}...")
    import shutil
    shutil.copy2(DB_PATH, backup_path)
    print(f"Backup created: {backup_path.stat().st_size / 1024 / 1024:.1f} MB")

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    # Ensure events table exists
    ensure_events_table(conn)

    # Count source rows
    total_source = conn.execute("SELECT COUNT(*) FROM event_logs").fetchone()[0]
    total_target_before = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    print(f"\nSource: event_logs has {total_source} rows")
    print(f"Target: events has {total_target_before} rows before migration")

    if limit:
        total_source = min(total_source, limit)
        print(f"Limit: processing {total_source} rows")

    # Migration loop
    start_time = time.time()
    total_inserted = 0
    total_skipped_existing = 0
    total_skipped_invalid = 0
    batch_num = 0

    offset = 0
    while offset < total_source:
        batch_num += 1
        inserted, skipped_ex, skipped_inv = migration_batch(
            conn, offset, batch_size, dry_run=dry_run
        )
        total_inserted += inserted
        total_skipped_existing += skipped_ex
        total_skipped_invalid += skipped_inv

        progress = min(offset + batch_size, total_source)
        pct = (progress / total_source) * 100 if total_source > 0 else 100
        print(f"  Batch {batch_num}: +{inserted} inserted, "
              f"{skipped_ex} existing, {skipped_inv} invalid "
              f"({progress}/{total_source} = {pct:.0f}%)")

        offset += batch_size

    elapsed = time.time() - start_time
    total_target_after = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] if not dry_run else total_target_before + total_inserted

    # Verification
    print(f"\n--- MIGRATION RESULTS ---")
    print(f"  Source rows processed: {total_source}")
    print(f"  Inserted:             {total_inserted}")
    print(f"  Skipped (existing):   {total_skipped_existing}")
    print(f"  Skipped (invalid):    {total_skipped_invalid}")
    print(f"  Events before:        {total_target_before}")
    print(f"  Events after:         {total_target_after}")
    print(f"  Duration:             {elapsed:.2f}s")
    print(f"  Batch size:           {batch_size}")
    print(f"  Dry run:              {dry_run}")

    # Per-type breakdown
    if not dry_run:
        print(f"\n--- PER-TYPE BREAKDOWN ---")
        for etype in ["ZONE", "ALERT", "DETECTION"]:
            src = conn.execute("SELECT COUNT(*) FROM event_logs WHERE event_type = ?", (etype,)).fetchone()[0]
            dst = conn.execute("SELECT COUNT(*) FROM events WHERE event_type = ?", (etype,)).fetchone()[0]
            print(f"  {etype}: source={src}, migrated={dst}")

    # Idempotency test
    if not dry_run and total_inserted > 0:
        print(f"\n--- IDEMPOTENCY TEST ---")
        test_inserted, test_skipped, _ = migration_batch(conn, 0, batch_size, dry_run=False)
        print(f"  Re-run: +{test_inserted} inserted, {test_skipped} skipped")
        print(f"  Idempotent: {'YES' if test_inserted == 0 else 'NO (PROBLEM)'}")

    conn.close()

    print(f"\n{'=' * 70}")
    print(f"MIGRATION {'COMPLETE (DRY RUN)' if dry_run else 'COMPLETE'}")
    print(f"{'=' * 70}")

    return {
        "source_rows": total_source,
        "inserted": total_inserted,
        "skipped_existing": total_skipped_existing,
        "skipped_invalid": total_skipped_invalid,
        "elapsed_seconds": elapsed,
        "dry_run": dry_run,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 3: Migrate event_logs to normalized events")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without writing")
    parser.add_argument("--batch-size", type=int, default=1000, help="Rows per batch (default: 1000)")
    parser.add_argument("--limit", type=int, default=None, help="Max rows to process")
    args = parser.parse_args()

    result = run_migration(dry_run=args.dry_run, batch_size=args.batch_size, limit=args.limit)
    sys.exit(0 if result["inserted"] >= 0 or result["dry_run"] else 1)
