#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Simple partner_change_requests update using pandas DataFrame
Direct read from PostgreSQL → Transform → Write back to PostgreSQL
"""

import pandas as pd
from sqlalchemy import create_engine, text
import json
from datetime import datetime

def read_partner_requests(connection_string='postgresql://postgres:admin123@localhost:5432/portal_dev'):
    """
    Read partner_change_requests table to DataFrame
    """
    engine = create_engine(connection_string)

    query = """
    SELECT * FROM partner_change_requests
    ORDER BY created_at DESC
    """

    df = pd.read_sql(query, engine)
    engine.dispose()

    print(f"✅ Loaded {len(df)} rows from partner_change_requests")
    return df

def write_partner_requests(df, connection_string='postgresql://postgres:admin123@localhost:5432/portal_dev',
                          mode='replace'):
    """
    Write DataFrame back to partner_change_requests table

    Parameters:
    - df: DataFrame to write
    - connection_string: PostgreSQL connection string
    - mode: 'replace' (drop and recreate), 'append' (add rows), 'update' (update existing rows)
    """
    engine = create_engine(connection_string)

    try:
        if mode == 'replace':
            # Drop and recreate table with all data
            df.to_sql('partner_change_requests', engine,
                     if_exists='replace',
                     index=False,
                     method='multi')
            print(f"✅ Replaced partner_change_requests with {len(df)} rows")

        elif mode == 'append':
            # Append new rows only
            df.to_sql('partner_change_requests', engine,
                     if_exists='append',
                     index=False,
                     method='multi')
            print(f"✅ Appended {len(df)} rows to partner_change_requests")

        elif mode == 'update':
            # Update existing rows based on request_number
            with engine.begin() as conn:
                for idx, row in df.iterrows():
                    # Convert row to dict and handle custom_data
                    row_dict = row.to_dict()

                    # Handle custom_data as JSONB
                    if 'custom_data' in row_dict:
                        if pd.isna(row_dict['custom_data']) or row_dict['custom_data'] == '':
                            row_dict['custom_data'] = '{}'
                        elif isinstance(row_dict['custom_data'], str):
                            try:
                                # Validate JSON
                                json.loads(row_dict['custom_data'])
                            except:
                                row_dict['custom_data'] = '{}'
                        elif isinstance(row_dict['custom_data'], dict):
                            row_dict['custom_data'] = json.dumps(row_dict['custom_data'])

                    # Update query
                    update_query = text("""
                        UPDATE partner_change_requests
                        SET requester_name = :requester_name,
                            requester_department = :requester_department,
                            company_name = :company_name,
                            business_number = :business_number,
                            change_type = :change_type,
                            current_value = :current_value,
                            new_value = :new_value,
                            change_reason = :change_reason,
                            status = :status,
                            custom_data = :custom_data::jsonb,
                            other_info = :other_info,
                            final_check_date = :final_check_date,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE request_number = :request_number
                    """)

                    conn.execute(update_query, row_dict)

                print(f"✅ Updated {len(df)} rows in partner_change_requests")

    except Exception as e:
        print(f"❌ Error writing to database: {e}")
        raise
    finally:
        engine.dispose()

def simple_transform_example(df):
    """
    Example transformation function
    Modify this to apply your transformations
    """
    # Generate request_number if missing (CRYYMMNNN format)
    if 'request_number' not in df.columns or df['request_number'].isna().any():
        from datetime import datetime
        yymm = datetime.now().strftime('%y%m')

        # Get existing numbers for this month
        engine = create_engine('postgresql://postgres:admin123@localhost:5432/portal_dev')
        existing = pd.read_sql(
            f"SELECT request_number FROM partner_change_requests WHERE request_number LIKE 'CR{yymm}%' ORDER BY request_number DESC LIMIT 1",
            engine
        )

        if not existing.empty:
            try:
                last_seq = int(existing.iloc[0]['request_number'][6:9])
            except:
                last_seq = 0
        else:
            last_seq = 0

        # Generate new numbers
        df['request_number'] = [f"CR{yymm}{i+last_seq+1:03d}" for i in range(len(df))]
        engine.dispose()

    # Example: Add other_info if missing
    if 'other_info' not in df.columns:
        df['other_info'] = '변경 요청 데이터'

    # Example: Set final_check_date to today if null
    if 'final_check_date' in df.columns:
        df['final_check_date'] = df['final_check_date'].fillna(datetime.now().date())

    # Example: Ensure custom_data is valid JSON string
    if 'custom_data' in df.columns:
        def fix_custom_data(val):
            if pd.isna(val) or val == '':
                return '{}'
            if isinstance(val, dict):
                return json.dumps(val)
            if isinstance(val, str):
                try:
                    json.loads(val)
                    return val
                except:
                    return '{}'
            return '{}'

        df['custom_data'] = df['custom_data'].apply(fix_custom_data)

    return df

def main():
    """
    Main workflow: Read → Transform → Write
    """
    print("=" * 60)
    print("Partner Change Requests - Simple Update")
    print("=" * 60)

    # 1. Read data
    print("\n1. Reading data from PostgreSQL...")
    df = read_partner_requests()

    # 2. Show sample data
    print("\n2. Sample data (first 3 rows):")
    print(df[['request_number', 'company_name', 'other_info', 'final_check_date']].head(3))

    # 3. Apply transformations
    print("\n3. Applying transformations...")
    df = simple_transform_example(df)

    # 4. Write back to database
    print("\n4. Writing back to database...")
    # Use 'update' to update existing rows only
    # Use 'replace' to drop and recreate entire table
    # Use 'append' to add new rows
    write_partner_requests(df, mode='update')

    print("\n✅ Complete!")

if __name__ == "__main__":
    # Example usage:
    # 1. Simple read and write back
    # df = read_partner_requests()
    # write_partner_requests(df, mode='update')

    # 2. With custom transformation
    # df = read_partner_requests()
    # df['other_info'] = 'Updated info'  # Your custom transformation
    # write_partner_requests(df, mode='update')

    # 3. Full workflow
    main()