
from db_connection import get_db_connection
from repositories.common.board_config import BOARD_CONFIGS

conn = get_db_connection()
print('is_postgres:', getattr(conn, 'is_postgres', None))  # True면 Postgres 연결

cur = conn.cursor()
table = BOARD_CONFIGS['subcontract_report']['section_table']
print('section_table:', table)

cur.execute(f"""
    SELECT section_key, section_name, section_order
    FROM {table}
    ORDER BY section_order
""")

rows = [dict(row) for row in cur.fetchall()]
print('rows:', rows)

cur.close()
conn.close()