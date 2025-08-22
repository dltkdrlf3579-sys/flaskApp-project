import sqlite3

conn = sqlite3.connect('portal.db')
cursor = conn.cursor()
cursor.execute('PRAGMA table_info(accidents_cache)')
print("accidents_cache 테이블 구조:")
for row in cursor.fetchall():
    print(row)
conn.close()