ALTER TABLE ai_training_material_files
    ADD COLUMN IF NOT EXISTS description TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS uploaded_at TIMESTAMP;

ALTER TABLE ai_training_material_files
    ALTER COLUMN uploaded_at SET DEFAULT CURRENT_TIMESTAMP;
