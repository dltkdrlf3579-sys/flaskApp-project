"""
Data synchronization service for external IQADB integration
Supports both real IQADB and mock data for development
"""

import os
import logging
import json
from datetime import datetime
from db_connection import get_db_connection
from db.upsert import safe_upsert

# Check if we should use mock data
USE_MOCK = os.environ.get('USE_MOCK', 'false').lower() in ['true', '1', 'yes']

def sync_safety_instructions():
    """Sync safety instructions from IQADB (or mock) to local DB"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get data from source
        if USE_MOCK:
            from mock_iqadb import get_mock_iqadb
            db = get_mock_iqadb()
            instructions = db.get_safety_instructions()
            logging.info(f"Using MOCK data for safety_instructions: {len(instructions)} items")
        else:
            # Real IQADB would be called here
            # For now, return empty since real integration not available
            logging.info("Real IQADB integration not configured, skipping sync")
            return {'success': True, 'count': 0, 'source': 'none'}
        
        # Sync each instruction to database
        count = 0
        for instr in instructions:
            # Prepare custom_data with all fields
            custom_data = {k: v for k, v in instr.items()}
            
            # Use safe_upsert to insert/update
            result = safe_upsert(
                conn,
                'safety_instructions',
                {'issue_number': instr['id']},  # Using issue_number as unique key
                {
                    'issue_number': instr['id'],
                    'custom_data': json.dumps(custom_data, ensure_ascii=False),
                    'created_at': datetime.now().isoformat(),
                    'is_deleted': 0
                }
            )
            if result:
                count += 1
        
        conn.commit()
        logging.info(f"Synced {count} safety instructions from {'MOCK' if USE_MOCK else 'IQADB'}")
        return {'success': True, 'count': count, 'source': 'mock' if USE_MOCK else 'iqadb'}
        
    except Exception as e:
        logging.error(f"Error syncing safety instructions: {e}")
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        conn.close()


def sync_follow_sop():
    """Sync Follow SOP data from IQADB (or mock) to local DB"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get data from source
        if USE_MOCK:
            from mock_iqadb import get_mock_iqadb
            db = get_mock_iqadb()
            sops = db.get_follow_sop()
            logging.info(f"Using MOCK data for follow_sop: {len(sops)} items")
        else:
            # Real IQADB would be called here
            logging.info("Real IQADB integration not configured, skipping sync")
            return {'success': True, 'count': 0, 'source': 'none'}
        
        # Sync each SOP to database
        count = 0
        for sop in sops:
            # Use work_req_no as primary key (or generate one)
            work_req_no = sop.get('id', f"SOP-{datetime.now().strftime('%Y%m%d%H%M%S')}-{count}")
            
            # Prepare custom_data
            custom_data = {k: v for k, v in sop.items() if k not in ['id', 'work_req_no']}
            
            # Use safe_upsert
            result = safe_upsert(
                conn,
                'follow_sop',
                {'work_req_no': work_req_no},
                {
                    'work_req_no': work_req_no,
                    'custom_data': json.dumps(custom_data, ensure_ascii=False),
                    'created_at': datetime.now().isoformat(),
                    'is_deleted': 0
                }
            )
            if result:
                count += 1
        
        conn.commit()
        logging.info(f"Synced {count} Follow SOP records from {'MOCK' if USE_MOCK else 'IQADB'}")
        return {'success': True, 'count': count, 'source': 'mock' if USE_MOCK else 'iqadb'}
        
    except Exception as e:
        logging.error(f"Error syncing Follow SOP: {e}")
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        conn.close()


def sync_full_process():
    """Sync Full Process data from IQADB (or mock) to local DB"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get data from source
        if USE_MOCK:
            from mock_iqadb import get_mock_iqadb
            db = get_mock_iqadb()
            processes = db.get_full_process()
            logging.info(f"Using MOCK data for full_process: {len(processes)} items")
        else:
            # Real IQADB would be called here
            logging.info("Real IQADB integration not configured, skipping sync")
            return {'success': True, 'count': 0, 'source': 'none'}
        
        # Sync each process to database
        count = 0
        for proc in processes:
            # Use fullprocess_number as primary key
            fullprocess_number = proc.get('id', f"FP-{datetime.now().strftime('%Y%m%d%H%M%S')}-{count}")
            
            # Prepare custom_data with all fields
            custom_data = {k: v for k, v in proc.items()}
            
            # Use safe_upsert
            result = safe_upsert(
                conn,
                'full_process',
                {'fullprocess_number': fullprocess_number},
                {
                    'fullprocess_number': fullprocess_number,
                    'custom_data': json.dumps(custom_data, ensure_ascii=False),
                    'created_at': datetime.now().isoformat(),
                    'is_deleted': 0
                }
            )
            if result:
                count += 1
        
        conn.commit()
        logging.info(f"Synced {count} Full Process records from {'MOCK' if USE_MOCK else 'IQADB'}")
        return {'success': True, 'count': count, 'source': 'mock' if USE_MOCK else 'iqadb'}
        
    except Exception as e:
        logging.error(f"Error syncing Full Process: {e}")
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        conn.close()


def sync_all():
    """Sync all data from IQADB (or mock)"""
    results = {
        'safety_instructions': sync_safety_instructions(),
        'follow_sop': sync_follow_sop(),
        'full_process': sync_full_process()
    }
    
    # Summary
    total_count = sum(r.get('count', 0) for r in results.values() if r.get('success'))
    all_success = all(r.get('success', False) for r in results.values())
    
    return {
        'success': all_success,
        'total_count': total_count,
        'details': results,
        'source': 'mock' if USE_MOCK else 'iqadb'
    }


# Command-line interface for testing
if __name__ == "__main__":
    import sys
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    if len(sys.argv) > 1:
        board = sys.argv[1]
        if board == 'all':
            result = sync_all()
        elif board == 'safety':
            result = sync_safety_instructions()
        elif board == 'sop':
            result = sync_follow_sop()
        elif board == 'process':
            result = sync_full_process()
        else:
            print(f"Unknown board: {board}")
            print("Usage: python data_sync_service.py [all|safety|sop|process]")
            sys.exit(1)
        
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("Usage: python data_sync_service.py [all|safety|sop|process]")
        print("Set USE_MOCK=true environment variable to use mock data")