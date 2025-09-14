#!/usr/bin/env python3
"""
Improve linked column types to be more specific and maintainable.

Changes:
- linked_text → linked_company_bizno, linked_person_id, etc.
- linked_dept → linked_person_dept, linked_contractor_dept, etc.

This makes the system more maintainable by clearly showing what each linked field connects to.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_connection import get_db_connection
import logging

logging.basicConfig(level=logging.INFO)

def analyze_linked_columns(cursor, table_name):
    """Analyze current linked columns and their relationships"""
    
    cursor.execute(f"""
        SELECT column_key, column_type, linked_columns 
        FROM {table_name}
        WHERE column_type IN ('linked_text', 'linked_dept', 'linked')
        ORDER BY column_order
    """)
    
    results = []
    for row in cursor.fetchall():
        column_key = row[0]
        column_type = row[1]
        linked_to = row[2]  # The main popup field this links to
        
        # Infer the main popup type from linked_columns field
        main_type = None
        if linked_to:
            cursor.execute(f"""
                SELECT column_type FROM {table_name}
                WHERE column_key = %s
            """, (linked_to,))
            main_row = cursor.fetchone()
            if main_row:
                main_popup_type = main_row[0]
                if 'popup_person' in main_popup_type:
                    main_type = 'person'
                elif 'popup_company' in main_popup_type:
                    main_type = 'company'
                elif 'popup_department' in main_popup_type:
                    main_type = 'department'
                elif 'popup_contractor' in main_popup_type:
                    main_type = 'contractor'
        
        # If no linked_columns, try to infer from column_key pattern
        if not main_type:
            base_key = column_key
            for suffix in ['_id', '_dept', '_department', '_bizno', '_code', '_company']:
                if column_key.endswith(suffix):
                    base_key = column_key[:-len(suffix)]
                    break
            
            # Check if base_key exists as a popup field
            cursor.execute(f"""
                SELECT column_type FROM {table_name}
                WHERE column_key = %s
            """, (base_key,))
            base_row = cursor.fetchone()
            if base_row:
                if 'popup_person' in base_row[0]:
                    main_type = 'person'
                elif 'popup_company' in base_row[0]:
                    main_type = 'company'
                elif 'popup_department' in base_row[0]:
                    main_type = 'department'
                elif 'popup_contractor' in base_row[0]:
                    main_type = 'contractor'
        
        # Determine new column_type based on pattern
        new_type = column_type  # Default to current
        
        if main_type:
            if column_key.endswith('_id'):
                new_type = f'linked_{main_type}_id'
            elif column_key.endswith('_dept') or column_key.endswith('_department'):
                new_type = f'linked_{main_type}_dept'
            elif column_key.endswith('_bizno') or column_key.endswith('_business_number'):
                new_type = f'linked_{main_type}_bizno'
            elif column_key.endswith('_code'):
                new_type = f'linked_{main_type}_code'
            elif column_key.endswith('_company'):
                new_type = f'linked_{main_type}_company'
            else:
                # Generic linked field for this main type
                new_type = f'linked_{main_type}_text'
        
        results.append({
            'column_key': column_key,
            'old_type': column_type,
            'new_type': new_type,
            'linked_to': linked_to,
            'main_type': main_type
        })
    
    return results

def update_column_types(cursor, table_name, changes):
    """Update column types to new specific types"""
    
    updated = 0
    for change in changes:
        if change['old_type'] != change['new_type']:
            cursor.execute(f"""
                UPDATE {table_name}
                SET column_type = %s
                WHERE column_key = %s
            """, (change['new_type'], change['column_key']))
            
            if cursor.rowcount > 0:
                updated += 1
                logging.info(f"Updated {change['column_key']}: {change['old_type']} → {change['new_type']}")
    
    return updated

def main():
    """Main function to improve linked types across all boards"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Tables to update
    tables = [
        'accident_column_config',
        'safety_instruction_column_config',
        'follow_sop_column_config',
        'full_process_column_config',
        'change_request_column_config'
    ]
    
    total_updated = 0
    
    for table in tables:
        try:
            logging.info(f"\n=== Processing {table} ===")
            
            # Check if table exists
            cursor.execute("""
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = %s
            """, (table,))
            
            if not cursor.fetchone():
                logging.warning(f"Table {table} does not exist, skipping")
                continue
            
            # Analyze current state
            changes = analyze_linked_columns(cursor, table)
            
            if not changes:
                logging.info(f"No linked columns found in {table}")
                continue
            
            # Show planned changes
            logging.info(f"Found {len(changes)} linked columns:")
            for change in changes:
                if change['old_type'] != change['new_type']:
                    logging.info(f"  {change['column_key']}: {change['old_type']} → {change['new_type']} (linked to: {change['linked_to']})")
                else:
                    logging.info(f"  {change['column_key']}: {change['old_type']} (no change needed)")
            
            # Apply changes
            updated = update_column_types(cursor, table, changes)
            total_updated += updated
            
            logging.info(f"Updated {updated} columns in {table}")
            
        except Exception as e:
            logging.error(f"Error processing {table}: {e}")
            conn.rollback()
            continue
    
    conn.commit()
    conn.close()
    
    logging.info(f"\n=== Summary ===")
    logging.info(f"Total columns updated: {total_updated}")
    logging.info("Linked column types have been improved for better maintainability!")

if __name__ == '__main__':
    main()