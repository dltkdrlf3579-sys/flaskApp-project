import sqlite3
from database_config import DatabaseConfig

DB_PATH = "portal.db"
db_config = DatabaseConfig()

# Test if external_db_enabled is False
print(f"external_db_enabled: {db_config.external_db_enabled}")

# Simulate what the function does
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

# Get dynamic columns
dynamic_columns_rows = conn.execute("""
    SELECT * FROM accident_column_config 
    WHERE is_active = 1 
    ORDER BY column_order
""").fetchall()
dynamic_columns = [dict(row) for row in dynamic_columns_rows]
print(f"Dynamic columns: {len(dynamic_columns)}")

# Get local accidents
all_accidents = []
try:
    local_accidents_rows = conn.execute("""
        SELECT * FROM accidents_cache 
        ORDER BY accident_date DESC, accident_number DESC
    """).fetchall()
    
    print(f"Local accidents found: {len(local_accidents_rows)}")
    
    for row in local_accidents_rows:
        accident = dict(row)
        if 'id' not in accident:
            accident['id'] = len(all_accidents) + 1000
        accident['accident_name'] = accident.get('accident_name') or f"사고_{accident['accident_number']}"
        accident['custom_data'] = accident.get('custom_data', '{}')
        all_accidents.append(accident)
    
    print(f"Total accidents after adding local: {len(all_accidents)}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

# Add dummy data if not external_db_enabled
if not db_config.external_db_enabled:
    print("Adding dummy data...")
    dummy_count = 0
    for i in range(50):
        dummy_count += 1
    print(f"Added {dummy_count} dummy accidents")
    
print(f"Final total would be: {len(all_accidents) + 50 if not db_config.external_db_enabled else len(all_accidents)}")

conn.close()