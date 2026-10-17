CREATE TABLE documents (id BIGSERIAL PRIMARY KEY, uploaded_by BIGINT NOT NULL REFERENCES users(id),
  title VARCHAR(255) NOT NULL, original_filename VARCHAR(255) NOT NULL, source_type VARCHAR(8) NOT NULL, mime_type VARCHAR(100),
  size_bytes BIGINT NOT NULL, storage_key VARCHAR(255) NOT NULL, status VARCHAR(12) NOT NULL DEFAULT 'UPLOADED', error_message TEXT,
  page_count INT, chunk_count INT, content_hash CHAR(64) NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(), ingested_at TIMESTAMPTZ);
CREATE INDEX idx_documents_status ON documents(status);
