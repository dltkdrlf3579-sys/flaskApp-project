#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Execute SQL to create iqadb test tables
"""

from db_connection import get_db_connection
import sys

def execute_sql_file(file_path):
    """Execute SQL commands from file"""
    try:
        # Read SQL file
        with open(file_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        # Connect to database
        conn = get_db_connection()
        cursor = conn.cursor()

        # Split by semicolons but preserve them
        sql_commands = []
        current_command = []
        lines = sql_content.split('\n')

        for line in lines:
            # Skip comments and empty lines
            if line.strip().startswith('--') or not line.strip():
                continue

            current_command.append(line)

            # Check if line ends with semicolon
            if line.rstrip().endswith(';'):
                sql_commands.append('\n'.join(current_command))
                current_command = []

        # Execute each command
        success_count = 0
        for i, cmd in enumerate(sql_commands, 1):
            if cmd.strip():
                try:
                    print(f"Executing command {i}...")
                    cursor.execute(cmd)
                    success_count += 1
                except Exception as e:
                    print(f"Error in command {i}: {e}")
                    print(f"Command was: {cmd[:100]}...")

        # Commit changes
        conn.commit()
        print(f"\nSuccessfully executed {success_count}/{len(sql_commands)} commands")

        # Verify tables were created
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'iqadb'
            ORDER BY table_name
        """)

        tables = cursor.fetchall()
        print("\nCreated tables in iqadb schema:")
        for (table,) in tables:
            print(f"  - iqadb.{table}")

        # Count rows in each table
        for (table,) in tables:
            try:
                cursor.execute(f'SELECT COUNT(*) FROM iqadb."{table}"')
                count = cursor.fetchone()[0]
                print(f"    Rows in {table}: {count}")
            except Exception as e:
                print(f"    Could not count rows in {table}: {e}")

        cursor.close()
        conn.close()

        print("\nTest tables created successfully!")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    execute_sql_file('create_iqadb_test_tables.sql')