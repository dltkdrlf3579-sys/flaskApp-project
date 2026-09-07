CREATE TABLE IF NOT EXISTS ai_training_materials (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    author_id TEXT NOT NULL,
    author_name TEXT NOT NULL,
    department_id TEXT NOT NULL DEFAULT '',
    department_name TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by TEXT NOT NULL,
    import_key TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS ai_training_material_files (
    id BIGSERIAL PRIMARY KEY,
    material_id BIGINT NOT NULL REFERENCES ai_training_materials(id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    storage_path TEXT NOT NULL UNIQUE,
    file_size BIGINT NOT NULL CHECK (file_size >= 0),
    sha256 TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ai_training_materials_updated
    ON ai_training_materials(updated_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_ai_training_material_files_material
    ON ai_training_material_files(material_id);
