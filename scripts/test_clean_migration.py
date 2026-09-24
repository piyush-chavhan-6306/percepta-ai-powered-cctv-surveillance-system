"""Test Alembic migration on a clean temporary database."""
import os
import sys
import sqlite3
import subprocess

TEST_DB = r'D:\SIH   border cctv\test_alembic_clean.db'

if os.path.exists(TEST_DB):
    os.remove(TEST_DB)

conn = sqlite3.connect(TEST_DB)
conn.close()
print(f"Created empty test DB: {TEST_DB}")

# Set env var for alembic env.py to pick up
test_url = f'sqlite:///{TEST_DB}'
env = os.environ.copy()
env['ALEMBIC_DATABASE_URL'] = test_url

result = subprocess.run(
    [r'D:\SIH   border cctv\venv\Scripts\python.exe', '-m', 'alembic', 'upgrade', 'head'],
    cwd=r'D:\SIH   border cctv',
    capture_output=True, text=True, timeout=60,
    env=env
)
print(f"STDOUT: {result.stdout}")
if result.stderr:
    print(f"STDERR: {result.stderr}")
print(f"Return code: {result.returncode}")

if result.returncode != 0:
    print("\n*** MIGRATION FAILED ***")
else:
    conn = sqlite3.connect(TEST_DB)
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"\nTables created: {len(tables)}")
    for t in tables:
        cursor2 = conn.execute(f"SELECT COUNT(*) FROM [{t}]")
        count = cursor2.fetchone()[0]
        cursor3 = conn.execute(f"PRAGMA table_info([{t}])")
        cols = [c[1] for c in cursor3.fetchall()]
        print(f"  [{t}] ({count} rows): {cols}")

    cursor = conn.execute("SELECT version_num FROM alembic_version")
    version = cursor.fetchone()
    print(f"\nAlembic version: {version[0] if version else 'NONE'}")

    for table in ['events', 'alerts', 'incidents', 'evidence', 'local_tracks']:
        cursor = conn.execute(f"PRAGMA foreign_key_list([{table}])")
        fks = cursor.fetchall()
        if fks:
            print(f"\n[{table}] FKs:")
            for fk in fks:
                print(f"  {fk[2]}.{fk[3]} -> {fk[4]}")

    expected = {
        'cameras', 'sessions', 'zones', 'global_entities', 'local_tracks',
        'detections', 'camera_transitions', 'events', 'incidents', 'alerts',
        'evidence', 'threat_assessments', 'face_observations', 'plate_observations',
        'weapon_observations', 'ai_queries', 'alembic_version'
    }
    missing = expected - set(tables)
    print(f"\nExpected: {len(expected)} | Created: {len(tables)} | Missing: {sorted(missing) if missing else 'NONE'}")

    if not missing:
        print("\n*** CLEAN DATABASE MIGRATION: PASS ***")
    else:
        print("\n*** CLEAN DATABASE MIGRATION: FAIL ***")

    conn.close()

# Cleanup
try:
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
        print(f"\nRemoved test DB")
except PermissionError:
    print(f"\nNote: Could not remove test DB (locked)")
