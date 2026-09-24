"""Verify Phase 1 DB is untouched."""
import sqlite3
conn = sqlite3.connect("percepta.db")
tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
print(f"Tables ({len(tables)}): {tables}")
row = conn.execute("SELECT version FROM alembic_version").fetchone()
print(f"Alembic head: {row[0] if row else 'NONE'}")
cnt = conn.execute("SELECT COUNT(*) FROM event_logs").fetchone()[0]
print(f"event_logs rows: {cnt}")
conn.close()
print("Phase 1 DB intact")
