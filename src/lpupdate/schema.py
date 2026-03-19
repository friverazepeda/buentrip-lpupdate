SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS companies (
  id BIGSERIAL PRIMARY KEY,
  canonical_name TEXT NOT NULL UNIQUE,
  aliases JSONB NOT NULL DEFAULT '[]'::jsonb,
  vehicles_json JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE companies
  ADD COLUMN IF NOT EXISTS vehicles_json JSONB NOT NULL DEFAULT '[]'::jsonb;

CREATE TABLE IF NOT EXISTS email_messages (
  id BIGSERIAL PRIMARY KEY,
  gmail_message_id TEXT NOT NULL UNIQUE,
  gmail_thread_id TEXT,
  subject TEXT,
  from_address TEXT,
  to_addresses JSONB NOT NULL DEFAULT '[]'::jsonb,
  label_names JSONB NOT NULL DEFAULT '[]'::jsonb,
  received_at TIMESTAMPTZ,
  snippet TEXT,
  body_text TEXT,
  body_html TEXT,
  raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS quarterly_updates (
  id BIGSERIAL PRIMARY KEY,
  company_id BIGINT REFERENCES companies(id),
  email_message_id BIGINT NOT NULL UNIQUE REFERENCES email_messages(id),
  report_period_label TEXT,
  report_quarter INT,
  report_year INT,
  received_at TIMESTAMPTZ,
  summary TEXT,
  metrics_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  highlights_json JSONB NOT NULL DEFAULT '[]'::jsonb,
  risks_json JSONB NOT NULL DEFAULT '[]'::jsonb,
  asks_json JSONB NOT NULL DEFAULT '[]'::jsonb,
  people_json JSONB NOT NULL DEFAULT '[]'::jsonb,
  confidence_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  parser_version TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS attachments (
  id BIGSERIAL PRIMARY KEY,
  email_message_id BIGINT NOT NULL REFERENCES email_messages(id),
  filename TEXT,
  mime_type TEXT,
  gmail_attachment_id TEXT,
  storage_path TEXT,
  extracted_text TEXT,
  metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""
