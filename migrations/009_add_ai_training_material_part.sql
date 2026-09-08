ALTER TABLE ai_training_materials
    ADD COLUMN IF NOT EXISTS part_name TEXT NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_ai_training_materials_part_updated
    ON ai_training_materials(part_name, updated_at DESC, id DESC);
