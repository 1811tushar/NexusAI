CREATE TABLE approvals (id BIGSERIAL PRIMARY KEY, investigation_id BIGINT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
  action_key VARCHAR(40) NOT NULL, action_type VARCHAR(24) NOT NULL, title VARCHAR(255) NOT NULL, description TEXT NOT NULL, params JSONB NOT NULL,
  risk VARCHAR(4) NOT NULL, rationale TEXT NOT NULL, evidence_keys JSONB NOT NULL DEFAULT '[]', status VARCHAR(10) NOT NULL DEFAULT 'PENDING',
  requested_at TIMESTAMPTZ NOT NULL DEFAULT now(), decided_by BIGINT REFERENCES users(id), decided_at TIMESTAMPTZ, comment TEXT, expires_at TIMESTAMPTZ NOT NULL,
  UNIQUE (investigation_id, action_key));
CREATE INDEX idx_approvals_status ON approvals(status);
CREATE TABLE action_log (id BIGSERIAL PRIMARY KEY, investigation_id BIGINT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
  approval_id BIGINT REFERENCES approvals(id), action_type VARCHAR(24) NOT NULL, params JSONB NOT NULL, risk VARCHAR(4) NOT NULL,
  status VARCHAR(10) NOT NULL, automatic BOOLEAN NOT NULL, note TEXT NOT NULL, executed_at TIMESTAMPTZ NOT NULL DEFAULT now());
