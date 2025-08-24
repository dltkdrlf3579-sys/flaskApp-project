import sqlite3

conn = sqlite3.connect('portal.db')
cursor = conn.cursor()

print("=== accident_column_config 테이블 ===")
results = cursor.execute("SELECT column_key, dropdown_options FROM accident_column_config WHERE column_key='column3'").fetchall()
for r in results:
    print(f"column_key: {r[0]}")
    print(f"dropdown_options: {r[1]}")

print("\n=== dropdown_option_codes 테이블 ===")
results = cursor.execute("SELECT option_code, option_value FROM dropdown_option_codes WHERE column_key='column3' ORDER BY display_order").fetchall()
for r in results:
    print(f"{r[0]}: {r[1]}")

conn.close()