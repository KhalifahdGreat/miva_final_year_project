-- =========================================================================
-- SME Chatbot — initial schema (migration 001)
-- =========================================================================
--
-- Run with:
--     psql $DATABASE_URL -f migrations/001_initial.sql
--
-- This file is intentionally Alembic-free for v1 so the schema is readable
-- in one place.  The migrations/versions/ folder is reserved for the
-- Alembic upgrade path once the project enters Sprint 2.

CREATE EXTENSION IF NOT EXISTS citext;

-- -------------------------------------------------------------------------
-- Identity
-- -------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS users (
    user_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email          CITEXT UNIQUE NOT NULL,
    display_name   TEXT,
    avatar_url     TEXT,
    auth_provider  TEXT NOT NULL,
    auth_subject   TEXT NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS users_provider_subject_uq
    ON users (auth_provider, auth_subject);

CREATE TABLE IF NOT EXISTS tenants (
    tenant_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_name  TEXT NOT NULL,
    slug           TEXT UNIQUE NOT NULL,
    plan           TEXT NOT NULL DEFAULT 'pilot',
    status         TEXT NOT NULL DEFAULT 'active',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tenant_memberships (
    tenant_id   UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    user_id     UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    role        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, user_id)
);

-- -------------------------------------------------------------------------
-- Configuration (versioned)
-- -------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS tenant_configs (
    tenant_id   UUID NOT NULL,
    version     INT  NOT NULL,
    data        JSONB NOT NULL,
    edited_by   UUID,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, version)
);
CREATE INDEX IF NOT EXISTS tenant_configs_recent_idx
    ON tenant_configs (tenant_id, version DESC);

-- -------------------------------------------------------------------------
-- Knowledge — document metadata
-- -------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS documents (
    document_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL,
    title           TEXT NOT NULL,
    document_type   TEXT NOT NULL,
    s3_key          TEXT,
    byte_size       BIGINT,
    mime_type       TEXT,
    chunk_count     INT NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'queued',
    error_message   TEXT,
    uploaded_by     UUID,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    archived_at     TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS documents_tenant_idx
    ON documents (tenant_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS manual_faqs (
    faq_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL,
    question      TEXT NOT NULL,
    answer        TEXT NOT NULL,
    language_hint TEXT,
    chunk_id      BIGINT,
    boost         REAL NOT NULL DEFAULT 1.5,
    created_by    UUID,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- -------------------------------------------------------------------------
-- Conversations + turns + audit
-- -------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS conversations (
    conversation_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        UUID NOT NULL,
    channel          TEXT NOT NULL,
    sender_id        TEXT NOT NULL,
    started_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_turn_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    turn_count       INT NOT NULL DEFAULT 0,
    languages_seen   TEXT[] NOT NULL DEFAULT '{}',
    UNIQUE (tenant_id, channel, sender_id)
);
CREATE INDEX IF NOT EXISTS conversations_recent_idx
    ON conversations (tenant_id, last_turn_at DESC);

CREATE TABLE IF NOT EXISTS turns (
    turn_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id    UUID NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
    tenant_id          UUID NOT NULL,
    role               TEXT NOT NULL,
    text               TEXT NOT NULL,
    received_at        TIMESTAMPTZ NOT NULL,
    detected_language  TEXT,
    is_mixed_language  BOOLEAN,
    escalated          BOOLEAN NOT NULL DEFAULT FALSE,
    escalation_reason  TEXT,
    outbound_status    TEXT,
    channel_msg_id     TEXT
);
CREATE INDEX IF NOT EXISTS turns_conv_idx ON turns (conversation_id, received_at);
CREATE INDEX IF NOT EXISTS turns_tenant_recent_idx ON turns (tenant_id, received_at DESC);

CREATE TABLE IF NOT EXISTS audit_records (
    audit_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id             UUID NOT NULL,
    conversation_id       UUID NOT NULL,
    turn_id               UUID NOT NULL,
    user_text             TEXT NOT NULL,
    detected_language     TEXT,
    is_mixed_language     BOOLEAN,
    retrieved_chunk_ids   BIGINT[] NOT NULL,
    retrieved_chunk_blob  TEXT,
    system_prompt         TEXT NOT NULL,
    user_prompt           TEXT NOT NULL,
    response_text         TEXT NOT NULL,
    model                 TEXT NOT NULL,
    provider              TEXT NOT NULL,
    prompt_tokens         INT,
    completion_tokens     INT,
    latency_breakdown_ms  JSONB NOT NULL,
    escalated             BOOLEAN NOT NULL,
    escalation_reason     TEXT,
    guard_mutations       TEXT[],
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS audit_tenant_idx
    ON audit_records (tenant_id, created_at DESC);

CREATE TABLE IF NOT EXISTS feedback (
    feedback_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        UUID NOT NULL,
    turn_id          UUID NOT NULL REFERENCES turns(turn_id) ON DELETE CASCADE,
    rating           TEXT NOT NULL,
    note             TEXT,
    corrected_answer TEXT,
    submitted_by     UUID,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS feedback_tenant_idx ON feedback (tenant_id, created_at DESC);

-- -------------------------------------------------------------------------
-- Channel credentials
-- -------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS tenant_whatsapp_credentials (
    tenant_id        UUID PRIMARY KEY REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    waba_id          TEXT NOT NULL,
    phone_number_id  TEXT NOT NULL UNIQUE,
    display_phone    TEXT,
    access_token_enc BYTEA NOT NULL,
    connected_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_event_at    TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS tenant_widget_keys (
    widget_key       TEXT PRIMARY KEY,
    tenant_id        UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    allowed_origins  TEXT[] NOT NULL DEFAULT '{}',
    revoked_at       TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- -------------------------------------------------------------------------
-- Idempotency
-- -------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS processed_messages (
    tenant_id       UUID NOT NULL,
    channel         TEXT NOT NULL,
    channel_msg_id  TEXT NOT NULL,
    processed_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, channel, channel_msg_id)
);
