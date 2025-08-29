#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enable WAL mode for SQLite database to prevent locks
"""
import sqlite3

DB_PATH = 'portal.db'

def enable_wal_mode():
    """Enable WAL mode for better concurrent access"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Enable WAL mode
    cursor.execute("PRAGMA journal_mode=WAL")
    result = cursor.fetchone()
    print(f"Journal mode set to: {result[0]}")
    
    # Check current settings
    cursor.execute("PRAGMA journal_mode")
    mode = cursor.fetchone()
    print(f"Current journal mode: {mode[0]}")
    
    # Set other optimizations
    cursor.execute("PRAGMA busy_timeout = 5000")  # 5 second timeout
    print("Set busy timeout to 5000ms")
    
    cursor.execute("PRAGMA synchronous = NORMAL")
    print("Set synchronous mode to NORMAL")
    
    conn.commit()
    conn.close()
    print("\nWAL mode enabled successfully!")

if __name__ == "__main__":
    enable_wal_mode()
