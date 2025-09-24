-- 004_create_attachments.sql
-- Phase 4: init_db 해체 작업 4/4 (첨부/공통 util 테이블)

CREATE TABLE IF NOT EXISTS attachments (
    id SERIAL PRIMARY KEY,
    board_type TEXT NOT NULL,
    item_key TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    mime_type TEXT,
    file_size bigint,
    description TEXT,
    uploaded_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_attachments_board_item ON attachments(board_type, item_key, is_deleted);
