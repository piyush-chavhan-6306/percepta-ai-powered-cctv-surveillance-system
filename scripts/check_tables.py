import sqlite3
conn = sqlite3.connect(r'D:\SIH   border cctv\percepta.db')
cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [row[0] for row in cursor.fetchall()]
print(f'Total tables: {len(tables)}')
for t in tables:
    cursor2 = conn.execute(f'SELECT COUNT(*) FROM [{t}]')
    count = cursor2.fetchone()[0]
    print(f'  {t}: {count} rows')
conn.close()
