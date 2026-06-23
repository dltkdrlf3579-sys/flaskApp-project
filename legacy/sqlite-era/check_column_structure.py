#!/usr/bin/env python3
"""
Check column structure in database
"""
from db_connection import get_db_connection

def check_column_structure():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Check full_process_column_config structure
    table = 'full_process_column_config'
    print(f"\n=== {table} structure ===")
    
    try:
        # For SQLite
        cur.execute(f"PRAGMA table_info({table})")
        columns = cur.fetchall()
        
        if columns:
            print("Columns in table:")
            for col in columns:
                print(f"  {col[1]}: {col[2]}")  # name: type
        else:
            # Try PostgreSQL way
            cur.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = %s
                ORDER BY ordinal_position
            """, (table.lower(),))
            columns = cur.fetchall()
            
            if columns:
                print("Columns in table:")
                for col in columns:
                    print(f"  {col[0]}: {col[1]}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Get a sample row
    print(f"\n=== Sample row from {table} ===")
    try:
        cur.execute(f"SELECT * FROM {table} LIMIT 1")
        row = cur.fetchone()
        if row:
            # Get column names
            col_names = [desc[0] for desc in cur.description]
            for i, name in enumerate(col_names):
                print(f"  {name}: {row[i]}")
    except Exception as e:
        print(f"Error: {e}")
    
    conn.close()

if __name__ == "__main__":
    check_column_structure()