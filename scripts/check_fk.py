"""Check FK enforcement and detailed table structure."""
import sqlite3

DB_PATH = r'D:\SIH   border cctv\percepta.db'
conn = sqlite3.connect(DB_PATH)

# Check if foreign_keys pragma is ON
cursor = conn.execute("PRAGMA foreign_keys")
fk_enabled = cursor.fetchone()[0]
print(f"Foreign keys enabled: {bool(fk_enabled)}")

# Check all indexes on alerts and incidents
for table in ['alerts', 'incidents', 'events']:
    cursor = conn.execute(f"PRAGMA index_list([{table}])")
    indexes = cursor.fetchall()
    print(f"\n[{table}] indexes:")
    for idx in indexes:
        name = idx[1]
        unique = idx[2]
        cursor2 = conn.execute(f"PRAGMA index_info([{name}])")
        cols = cursor2.fetchall()
        col_names = [c[2] for c in cols]
        print(f"  {name} (unique={unique}): {col_names}")

# Check FKs on events table
cursor = conn.execute("PRAGMA foreign_key_list([events])")
fks = cursor.fetchall()
print(f"\n[events] foreign keys:")
for fk in fks:
    print(f"  {fk}")

# Verify backup exists and is valid
import os
import hashlib
backup_path = r'D:\SIH   border cctv\percepta.db.backup_phase1_20260910_214230'
if os.path.exists(backup_path):
    size = os.path.getsize(backup_path)
    with open(backup_path, 'rb') as f:
        md5 = hashlib.md5(f.read()).hexdigest()
    print(f"\nBackup exists: {size} bytes, MD5: {md5}")
else:
    print(f"\nBackup NOT FOUND at {backup_path}")

# Check current DB size and MD5
with open(DB_PATH, 'rb') as f:
    data = f.read()
print(f"Current DB: {len(data)} bytes, MD5: {hashlib.md5(data).hexdigest()}")

conn.close()
