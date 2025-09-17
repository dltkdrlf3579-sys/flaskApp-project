#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Simulate ID generation to verify the logic is correct
"""

import psycopg2
from datetime import datetime, timedelta
import random

def simulate_id_generation():
    """Simulate the ID generation process"""

    conn = psycopg2.connect(
        "postgresql://postgres:admin123@localhost:5432/portal_dev"
    )
    cursor = conn.cursor()

    print("=" * 60)
    print("Simulating ID Generation")
    print("=" * 60)

    # Clear existing test data
    cursor.execute("DELETE FROM follow_sop WHERE work_req_no LIKE 'FS2509%'")
    cursor.execute("DELETE FROM full_process WHERE fullprocess_number LIKE 'FP2509%'")
    conn.commit()

    # Simulate inserting records with the new ID format
    print("\n1. Simulating FollowSOP records:")

    # Generate records for different dates
    dates = [
        datetime(2025, 9, 15),
        datetime(2025, 9, 16),
        datetime(2025, 9, 17),
    ]

    date_counters = {}

    for date_obj in dates:
        date_str = date_obj.strftime('%y%m%d')
        print(f"\n   Date: {date_str}")

        # Simulate 5 records per date
        for i in range(5):
            # Check if we have a counter for this date
            if date_str in date_counters:
                new_counter = date_counters[date_str] + 1
            else:
                # Query for the last counter
                pattern = f'FS{date_str}%'
                cursor.execute('''
                    SELECT work_req_no FROM follow_sop
                    WHERE work_req_no LIKE %s
                    ORDER BY work_req_no DESC
                    LIMIT 1
                ''', (pattern,))

                last_result = cursor.fetchone()
                if last_result and len(last_result[0]) == 12:
                    try:
                        last_counter = int(last_result[0][8:12])
                        new_counter = last_counter + 1
                    except ValueError:
                        new_counter = 1
                else:
                    new_counter = 1

            date_counters[date_str] = new_counter
            work_req_no = f'FS{date_str}{new_counter:04d}'

            # Insert the record
            created_at = date_obj + timedelta(hours=i, minutes=random.randint(0, 59))
            cursor.execute('''
                INSERT INTO follow_sop (work_req_no, custom_data, created_at, is_deleted)
                VALUES (%s, '{}', %s, 0)
                ON CONFLICT (work_req_no) DO NOTHING
            ''', (work_req_no, created_at))

            print(f"   - {work_req_no} (created: {created_at})")

    print("\n2. Simulating FullProcess records:")

    date_counters = {}

    for date_obj in dates:
        date_str = date_obj.strftime('%y%m%d')
        print(f"\n   Date: {date_str}")

        # Simulate 5 records per date
        for i in range(5):
            # Check if we have a counter for this date
            if date_str in date_counters:
                new_counter = date_counters[date_str] + 1
            else:
                # Query for the last counter
                pattern = f'FP{date_str}%'
                cursor.execute('''
                    SELECT fullprocess_number FROM full_process
                    WHERE fullprocess_number LIKE %s
                    ORDER BY fullprocess_number DESC
                    LIMIT 1
                ''', (pattern,))

                last_result = cursor.fetchone()
                if last_result and len(last_result[0]) == 13:
                    try:
                        last_counter = int(last_result[0][8:13])
                        new_counter = last_counter + 1
                    except ValueError:
                        new_counter = 1
                else:
                    new_counter = 1

            date_counters[date_str] = new_counter
            fullprocess_number = f'FP{date_str}{new_counter:05d}'

            # Insert the record
            created_at = date_obj + timedelta(hours=i, minutes=random.randint(0, 59))
            cursor.execute('''
                INSERT INTO full_process (fullprocess_number, custom_data, created_at, is_deleted)
                VALUES (%s, '{}', %s, 0)
                ON CONFLICT (fullprocess_number) DO NOTHING
            ''', (fullprocess_number, created_at))

            print(f"   - {fullprocess_number} (created: {created_at})")

    conn.commit()

    # Verify the results
    print("\n3. Verifying results:")

    print("\n   FollowSOP records:")
    cursor.execute('''
        SELECT work_req_no, created_at, LENGTH(work_req_no)
        FROM follow_sop
        WHERE work_req_no LIKE 'FS2509%'
        ORDER BY work_req_no
    ''')

    for row in cursor.fetchall():
        status = "OK" if row[2] == 12 else "ERROR"
        print(f"   {status} {row[0]} | {row[1]} | Length: {row[2]}")

    print("\n   FullProcess records:")
    cursor.execute('''
        SELECT fullprocess_number, created_at, LENGTH(fullprocess_number)
        FROM full_process
        WHERE fullprocess_number LIKE 'FP2509%'
        ORDER BY fullprocess_number
    ''')

    for row in cursor.fetchall():
        status = "OK" if row[2] == 13 else "ERROR"
        print(f"   {status} {row[0]} | {row[1]} | Length: {row[2]}")

    # Check for continuity
    print("\n4. Checking sequence continuity:")

    for prefix, table, column, length in [
        ('FS', 'follow_sop', 'work_req_no', 12),
        ('FP', 'full_process', 'fullprocess_number', 13)
    ]:
        print(f"\n   {prefix} sequences:")
        for date_obj in dates:
            date_str = date_obj.strftime('%y%m%d')
            pattern = f'{prefix}{date_str}%'

            cursor.execute(f'''
                SELECT {column}
                FROM {table}
                WHERE {column} LIKE %s
                AND LENGTH({column}) = %s
                ORDER BY {column}
            ''', (pattern, length))

            results = cursor.fetchall()
            if results:
                if prefix == 'FS':
                    counters = [int(r[0][8:12]) for r in results]
                else:  # FP
                    counters = [int(r[0][8:13]) for r in results]

                expected = set(range(1, max(counters) + 1))
                actual = set(counters)
                gaps = expected - actual

                if gaps:
                    print(f"   {date_str}: {len(results)} records, gaps at: {sorted(gaps)}")
                else:
                    print(f"   {date_str}: {len(results)} records, continuous (1-{max(counters)})")

    cursor.close()
    conn.close()

    print("\n" + "=" * 60)
    print("Simulation Complete")
    print("=" * 60)

if __name__ == "__main__":
    simulate_id_generation()