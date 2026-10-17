CREATE TABLE investigations (id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL REFERENCES users(id), question TEXT NOT NULL,
  status VARCHAR(18) NOT NULL DEFAULT 'RUNNING', options JSONB NOT NULL DEFAULT '{}', thread_id UUID NOT NULL UNIQUE,
  plan JSONB NOT NULL DEFAULT '[]', report_markdown TEXT, summary TEXT, confidence NUMERIC(4,3), loops_used INT NOT NULL DEFAULT 0,
  recommendations JSONB NOT NULL DEFAULT '[]', usage JSONB, latency_ms INT, error_message TEXT, feedback_rating SMALLINT, feedback_comment TEXT,
  last_seq INT NOT NULL DEFAULT 0, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), completed_at TIMESTAMPTZ);
CREATE INDEX idx_inv_user_created ON investigations(user_id, created_at DESC);
CREATE INDEX idx_inv_status ON investigations(status);
CREATE TABLE agent_steps (id BIGSERIAL PRIMARY KEY, investigation_id BIGINT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
  seq INT NOT NULL, type VARCHAR(30) NOT NULL, payload JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE (investigation_id, seq));
CREATE TABLE evidence (id BIGSERIAL PRIMARY KEY, investigation_id BIGINT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
  evidence_key UUID NOT NULL, kind VARCHAR(10) NOT NULL, title VARCHAR(255) NOT NULL, snippet TEXT NOT NULL, source JSONB NOT NULL DEFAULT '{}',
  data JSONB, chart JSONB, score NUMERIC(5,4), created_at TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE (investigation_id, evidence_key));
CREATE TABLE claims (id BIGSERIAL PRIMARY KEY, investigation_id BIGINT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
  claim_key VARCHAR(40) NOT NULL, text TEXT NOT NULL, status VARCHAR(12) NOT NULL, confidence NUMERIC(4,3) NOT NULL, is_key BOOLEAN NOT NULL DEFAULT FALSE,
  evidence_keys JSONB NOT NULL DEFAULT '[]', loop INT NOT NULL DEFAULT 0, created_at TIMESTAMPTZ NOT NULL DEFAULT now());  -- latest verification per claim_key wins in the API
