from db_connection import get_db_connection

def execute_sql():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    with open('create_permission_requests_table.sql', 'r', encoding='utf-8') as f:
        sql = f.read()
    
    # Split and execute commands
    commands = sql.split(';')
    for cmd in commands:
        if cmd.strip():
            try:
                cursor.execute(cmd)
                print(f"Executed: {cmd[:50]}...")
            except Exception as e:
                print(f"Error: {e}")
    
    conn.commit()
    cursor.close()
    conn.close()
    print("Permission requests tables created successfully")

if __name__ == "__main__":
    execute_sql()
