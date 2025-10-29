-- Migration: Add file_path and mime_type columns to partner_attachments table
-- Date: 2025-01-04

-- Check if table exists and alter it
-- SQLite doesn't support ALTER TABLE ADD COLUMN IF NOT EXISTS, so we need to handle this carefully

-- Create the table if it doesn't exist with all columns
CREATE TABLE IF NOT EXISTS partner_attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_number TEXT NOT NULL,
    file_path TEXT,
    filename TEXT NOT NULL,
    original_filename TEXT,
    mime_type TEXT,
    file_size INTEGER,
    upload_date TEXT DEFAULT (datetime('now'))
);

-- For existing tables, we need to add the missing columns
-- Note: This will fail if columns already exist, which is fine
-- Run each ALTER TABLE separately in your migration tool

-- Try to add file_path column (will fail if exists, that's OK)
ALTER TABLE partner_attachments ADD COLUMN file_path TEXT;

-- Try to add mime_type column (will fail if exists, that's OK)
ALTER TABLE partner_attachments ADD COLUMN mime_type TEXT;