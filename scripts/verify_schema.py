"""Inspect actual SQLite schema in percepta.db — read-only."""
import sqlite3
import hashlib

DB_PATH = r'D:\SIH   border cctv\percepta.db'

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

# 1. List ALL physical tables
print("=" * 60)
print("PHYSICAL TABLES IN SQLite")
print("=" * 60)
cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [row['name'] for row in cursor.fetchall()]
for t in tables:
    print(f"  {t}")

# 2. For each table, show columns and row count
print("\n" + "=" * 60)
print("TABLE DETAILS")
print("=" * 60)
for t in tables:
    cursor = conn.execute(f"PRAGMA table_info([{t}])")
    cols = cursor.fetchall()
    cursor2 = conn.execute(f"SELECT COUNT(*) as cnt FROM [{t}]")
    count = cursor2.fetchone()['cnt']
    col_names = [c['name'] for c in cols]
    print(f"\n  [{t}] — {count} rows")
    print(f"    Columns: {col_names}")

# 3. Check for table name collisions
print("\n" + "=" * 60)
print("COLLISION CHECK")
print("=" * 60)
# The new schema defines these table names:
new_schema_tables = {
    'cameras', 'sessions', 'zones', 'global_entities', 'local_tracks',
    'detections', 'camera_transitions', 'events', 'incidents', 'alerts',
    'evidence', 'threat_assessments', 'face_observations', 'plate_observations',
    'weapon_observations', 'ai_queries'
}
legacy_tables = {'event_logs'}  # The known legacy table

physical_set = set(tables)
collisions = physical_set & new_schema_tables
print(f"  Physical tables: {sorted(physical_set)}")
print(f"  New schema tables: {sorted(new_schema_tables)}")
print(f"  Known legacy: {sorted(legacy_tables)}")

# Check which new schema tables actually exist physically
exist_new = physical_set & new_schema_tables
missing_new = new_schema_tables - physical_set
print(f"\n  New schema tables that EXIST: {sorted(exist_new)}")
print(f"  New schema tables MISSING: {sorted(missing_new)}")

# Check if legacy tables exist
exist_legacy = physical_set & legacy_tables
print(f"  Legacy tables that EXIST: {sorted(exist_legacy)}")

# Check for duplicate table names (collision)
# In SQLite, you can't have two tables with the same name
# So if 'alerts' exists, there's only ONE 'alerts' table
print(f"\n  Any table name appears twice? NO (SQLite forbids it)")

# 4. Check which ORM model maps to which table
print("\n" + "=" * 60)
print("ORM MODEL → TABLE MAPPING")
print("=" * 60)
# Import ORM models to check __tablename__
import sys
sys.path.insert(0, r'D:\SIH   border cctv')
from backend.database.schema import (
    Camera, Session, Zone, Detection, LocalTrack, GlobalEntity,
    CameraTransition, Event, Incident, Alert, Evidence,
    ThreatAssessment, FaceObservation, PlateObservation,
    WeaponObservation, AIQuery
)
from backend.incidents.models import EventLogModel

models = [
    ("Camera", Camera),
    ("Session", Session),
    ("Zone", Zone),
    ("Detection", Detection),
    ("LocalTrack", LocalTrack),
    ("GlobalEntity", GlobalEntity),
    ("CameraTransition", CameraTransition),
    ("Event (new)", Event),
    ("Incident (new)", Incident),
    ("Alert (new)", Alert),
    ("Evidence", Evidence),
    ("ThreatAssessment", ThreatAssessment),
    ("FaceObservation", FaceObservation),
    ("PlateObservation", PlateObservation),
    ("WeaponObservation", WeaponObservation),
    ("AIQuery", AIQuery),
    ("EventLogModel (legacy)", EventLogModel),
]

for name, model in models:
    tbl = model.__tablename__
    exists = tbl in physical_set
    print(f"  {name:25s} → __tablename__={tbl:25s}  physical={'YES' if exists else 'NO'}")

# 5. Check if legacy incidents/alerts tables exist
print("\n" + "=" * 60)
print("LEGACY TABLE CHECK")
print("=" * 60)
# Check if there's a legacy 'incidents' or 'alerts' table from the old schema
for t in ['incidents', 'alerts', 'event_logs']:
    cursor = conn.execute(f"SELECT COUNT(*) as cnt FROM [{t}]")
    count = cursor.fetchone()['cnt']
    print(f"  [{t}]: {count} rows")

# 6. Compute MD5 of database file for integrity
conn.close()

with open(DB_PATH, 'rb') as f:
    data = f.read()
md5 = hashlib.md5(data).hexdigest()
size_mb = len(data) / (1024 * 1024)
print(f"\n  Database file size: {size_mb:.1f} MB")
print(f"  MD5: {md5}")
