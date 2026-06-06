# Data Model

This document is the canonical reference for **what is stored where**. It covers:

- PostgreSQL schemas with row-level security (RLS).
- Vector database collection schemas.
- Object storage layout.
- Redis cache layout.
- Migration strategy.
- Backup and retention.

---

## Table of Contents

1. [Storage Map](#1-storage-map)
2. [PostgreSQL Schema](#2-postgresql-schema)
3. [Row-Level Security](#3-row-level-security)
4. [Vector Database Schema](#4-vector-database-schema)
5. [Object Storage Layout](#5-object-storage-layout)
6. [Redis Cache Layout](#6-redis-cache-layout)
7. [Migration Strategy](#7-migration-strategy)
8. [Backup, Retention, and Erasure](#8-backup-retention-and-erasure)
9. [Tenant Provisioning Procedure](#9-tenant-provisioning-procedure)

---

## 1. Storage Map

| Concern | System | Notes |
|---|---|---|
| Tenants, users, configs, conversations, audit, feedback | PostgreSQL 16 | RLS-enforced isolation |
| Embeddings + retrievable text chunks | Milvus (Lite for MVP, Cluster for scale) **or** pgvector | One collection per tenant |
| Raw uploads (PDF / DOCX / CSV / XLSX), audit archives, backups | Cloudflare R2 (S3-compatible) | Versioning enabled |
| Conversation history (recent), config cache, embedder warm cache, RQ queue, rate-limit counters | Redis 7 | TTL-driven |

---

## 2. PostgreSQL Schema

All tables use UUID primary keys, `created_at` and `updated_at` timestamps with timezone, and a `tenant_id UUID NOT NULL` column where relevant.

### 2.1 Identity

```sql
CREATE TABLE users (
    user_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email          CITEXT UNIQUE NOT NULL,
    display_name   TEXT,
    avatar_url     TEXT,
    auth_provider  TEXT NOT NULL,               -- 'clerk', 'auth_js', 'google'
    auth_subject   TEXT NOT NULL,               -- provider's user id
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX users_provider_subject_uq
    ON users (auth_provider, auth_subject);
```

```sql
CREATE TABLE tenants (
    tenant_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_name  TEXT NOT NULL,
    slug           TEXT UNIQUE NOT NULL,         -- URL-safe handle
    plan           TEXT NOT NULL DEFAULT 'pilot', -- 'pilot' | 'paid' (future)
    status         TEXT NOT NULL DEFAULT 'active', -- 'active' | 'suspended' | 'archived'
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

```sql
CREATE TABLE tenant_memberships (
    tenant_id   UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    user_id     UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    role        TEXT NOT NULL,                  -- 'owner' | 'staff'
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, user_id)
);
```

### 2.2 Configuration

```sql
CREATE TABLE tenant_configs (
    tenant_id   UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    version     INT  NOT NULL,
    data        JSONB NOT NULL,                  -- full TenantConfig payload
    edited_by   UUID REFERENCES users(user_id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, version)
);
CREATE INDEX tenant_configs_tenant_idx ON tenant_configs (tenant_id, version DESC);
```

The `data` payload follows the JSON schema in `02_CORE_ENGINE.md` §4.1. New saves create a new row; rollback is "load older row, save as a new version".

### 2.3 Knowledge — document metadata

The vector store holds embeddings + text. Postgres holds the document-level metadata so the dashboard can list documents without touching the vector DB.

```sql
CREATE TABLE documents (
    document_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    document_type   TEXT NOT NULL,    -- 'catalogue'|'faq'|'policy'|'manual_faq'|'pricing'
    s3_key          TEXT NOT NULL,
    byte_size       BIGINT NOT NULL,
    mime_type       TEXT,
    chunk_count     INT NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'queued',
                     -- 'queued'|'ingesting'|'ready'|'failed'|'archived'
    error_message   TEXT,
    uploaded_by     UUID REFERENCES users(user_id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    archived_at     TIMESTAMPTZ
);
CREATE INDEX documents_tenant_status_idx
    ON documents (tenant_id, status, created_at DESC);
```

Note: chunk text + embedding live in the vector DB. We only store a foreign-key-style `chunk_id` reference here when needed for audit. (Most chunks are referenced from the `audit_records` table.)

### 2.4 Manual FAQ (curated answers)

```sql
CREATE TABLE manual_faqs (
    faq_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    question      TEXT NOT NULL,
    answer        TEXT NOT NULL,
    language_hint TEXT,                          -- 'en'|'pid'|'yo'|'ha'|'ig'
    chunk_id      BIGINT,                         -- corresponding chunk id in vector store
    boost         REAL NOT NULL DEFAULT 1.5,
    created_by    UUID REFERENCES users(user_id),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 2.5 Conversations and turns

```sql
CREATE TABLE conversations (
    conversation_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    channel          TEXT NOT NULL,             -- 'whatsapp'|'widget'
    sender_id        TEXT NOT NULL,             -- WhatsApp wa_id or widget session uuid
    started_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_turn_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    turn_count       INT NOT NULL DEFAULT 0,
    languages_seen   TEXT[] NOT NULL DEFAULT '{}',
    UNIQUE (tenant_id, channel, sender_id)
);
CREATE INDEX conversations_tenant_recent_idx
    ON conversations (tenant_id, last_turn_at DESC);
```

```sql
CREATE TABLE turns (
    turn_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id   UUID NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
    tenant_id         UUID NOT NULL,            -- denormalised for RLS
    role              TEXT NOT NULL,            -- 'user' | 'assistant'
    text              TEXT NOT NULL,
    received_at       TIMESTAMPTZ NOT NULL,
    detected_language TEXT,
    is_mixed_language BOOLEAN,
    escalated         BOOLEAN NOT NULL DEFAULT FALSE,
    escalation_reason TEXT,
    outbound_status   TEXT,                     -- 'sent'|'delivered'|'read'|'failed'
    parent_msg_id     TEXT,                     -- Meta wamid for inbound, our id for outbound
    channel_msg_id    TEXT
);
CREATE INDEX turns_conv_idx ON turns (conversation_id, received_at);
CREATE INDEX turns_tenant_recent_idx ON turns (tenant_id, received_at DESC);
```

### 2.6 Audit (research-grade)

The audit table is dense — it stores everything an evaluator could ever ask for after the fact (re-run with a different model, re-grade with new annotators, etc.). It is the most important table for the thesis.

```sql
CREATE TABLE audit_records (
    audit_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id             UUID NOT NULL,
    conversation_id       UUID NOT NULL,
    turn_id               UUID NOT NULL,
    user_text             TEXT NOT NULL,
    detected_language     TEXT,
    is_mixed_language     BOOLEAN,
    retrieved_chunk_ids   BIGINT[] NOT NULL,
    retrieved_chunk_blob  TEXT,                  -- joined chunk text for fast re-grading
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
    guard_mutations       TEXT[],                -- e.g. ['pii_redacted']
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX audit_tenant_created_idx
    ON audit_records (tenant_id, created_at DESC);
```

### 2.7 Feedback

```sql
CREATE TABLE feedback (
    feedback_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        UUID NOT NULL,
    turn_id          UUID NOT NULL REFERENCES turns(turn_id) ON DELETE CASCADE,
    rating           TEXT NOT NULL,             -- 'up' | 'down'
    note             TEXT,
    corrected_answer TEXT,                       -- staff-provided fix; flows back to KB
    submitted_by     UUID REFERENCES users(user_id),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX feedback_tenant_idx ON feedback (tenant_id, created_at DESC);
```

A trigger / worker promotes any `corrected_answer` to a boosted manual-FAQ chunk.

### 2.8 Channels

```sql
CREATE TABLE tenant_whatsapp_credentials (
    tenant_id        UUID PRIMARY KEY REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    waba_id          TEXT NOT NULL,
    phone_number_id  TEXT NOT NULL UNIQUE,
    display_phone    TEXT,
    access_token_enc BYTEA NOT NULL,            -- encrypted at rest, KMS-backed
    connected_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_event_at    TIMESTAMPTZ
);

CREATE TABLE tenant_widget_keys (
    widget_key       TEXT PRIMARY KEY,           -- pk_live_...
    tenant_id        UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    allowed_origins  TEXT[] NOT NULL DEFAULT '{}',
    revoked_at       TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 2.9 Idempotency

```sql
CREATE TABLE processed_messages (
    tenant_id       UUID NOT NULL,
    channel         TEXT NOT NULL,
    channel_msg_id  TEXT NOT NULL,
    processed_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, channel, channel_msg_id)
);
-- TTL via partitioning or a daily DELETE for rows older than 7 days.
```

### 2.10 Operational

```sql
CREATE TABLE escalation_events (
    event_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL,
    turn_id         UUID NOT NULL,
    reason          TEXT NOT NULL,
    delivered_to    TEXT,                       -- email / phone / dashboard alert id
    delivery_status TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE rate_limits (
    bucket_key   TEXT PRIMARY KEY,              -- e.g. 'tenant:<id>:msg:<minute>'
    counter      INT  NOT NULL DEFAULT 0,
    expires_at   TIMESTAMPTZ NOT NULL
);
-- Or move this entirely to Redis; if so, drop the table.
```

---

## 3. Row-Level Security

Every tenant-owned table has RLS enabled. Pattern:

```sql
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_conversations
    ON conversations
    USING (tenant_id::text = current_setting('app.current_tenant', true));
```

The application sets the current tenant per request, inside a transaction:

```python
with db.transaction() as tx:
    tx.execute("SET LOCAL app.current_tenant = %s", (str(tenant_id),))
    # all subsequent queries on tenant tables are scoped automatically
```

Migrations run as a superuser (RLS bypassed). A separate **app role** does runtime queries; RLS applies to it.

> Why RLS in addition to per-collection vector isolation? Defence in depth. If application code ever forgets a `WHERE tenant_id = ?` clause on a SQL query, RLS keeps the data isolated. The policy is so cheap to define that there's no reason not to use it.

---

## 4. Vector Database Schema

### 4.1 Per-tenant collections

One collection per tenant: `kb_<tenant_id_short>` where `tenant_id_short` is the first 12 hex chars of the tenant's UUID.

### 4.2 Collection schema

```python
fields = [
    FieldSchema("id",            DataType.INT64,        is_primary=True, auto_id=True),
    FieldSchema("embedding",     DataType.FLOAT_VECTOR, dim=1024),     # e5-large or bge-m3
    FieldSchema("text",          DataType.VARCHAR,      max_length=8192),
    FieldSchema("document_id",   DataType.VARCHAR,      max_length=64),
    FieldSchema("document_type", DataType.VARCHAR,      max_length=32),
    FieldSchema("section",       DataType.VARCHAR,      max_length=128),
    FieldSchema("language_hint", DataType.VARCHAR,      max_length=8),
    FieldSchema("boost",         DataType.FLOAT),
    FieldSchema("metadata_json", DataType.VARCHAR,      max_length=4096),
    FieldSchema("created_at",    DataType.INT64),                       # epoch ms
    FieldSchema("deleted",       DataType.BOOL),                        # soft-delete
]
schema = CollectionSchema(fields=fields, enable_dynamic_field=True)

index = {
    "field_name": "embedding",
    "index_type": "HNSW",       # or 'IVF_FLAT' for small collections
    "metric_type": "COSINE",
    "params": {"M": 16, "efConstruction": 200},
}
```

### 4.3 Search filter convention

All queries pass `filter='deleted == false'`. (Soft-deletes preserve audit traceability.)

### 4.4 Capacity expectations

- Average SME corpus: ~300 chunks × ~512 tokens × 4 bytes/token ≈ 600 KB raw text per tenant.
- Embedding storage: `1024 dims × 4 bytes × 300 chunks ≈ 1.2 MB` per tenant.
- 100 tenants ≈ 120 MB embeddings — trivial for Milvus Lite.

### 4.5 If pgvector instead

If consolidating on Postgres at scale, the same schema becomes a Postgres table with `vector(1024)` and a `tenant_id UUID` column under RLS. Index: `CREATE INDEX ... USING hnsw (embedding vector_cosine_ops)`. Trade-off discussion in `00 §10.2`.

---

## 5. Object Storage Layout

Single bucket per environment: `<env>-tenant-uploads`.

Object keys:

```
tenants/<tenant_id>/uploads/<document_id>/<original_filename>
tenants/<tenant_id>/uploads/<document_id>/extracted.txt    (post-extract cache)
tenants/<tenant_id>/audit/<yyyy>/<mm>/<dd>/<archive>.jsonl.gz
backups/postgres/<yyyy>-<mm>-<dd>.dump
backups/vector/<yyyy>-<mm>-<dd>/<tenant_id>.snapshot
```

Bucket settings:

- **Versioning:** enabled.
- **Public access:** blocked.
- **Lifecycle rule:** delete `tenants/*/uploads/*/extracted.txt` 30 days after last-access (it's a regenerable cache).
- **Lifecycle rule:** transition `backups/*` older than 30 days to colder R2 tier.

Access:

- Application service has a scoped IAM token to read/write under `tenants/`.
- No tenant ever receives raw R2 credentials; uploads are streamed through the API or via short-lived **pre-signed URLs** generated server-side.

---

## 6. Redis Cache Layout

Keyspace conventions:

| Key pattern | TTL | Purpose |
|---|---|---|
| `tcfg:<tenant_id>` | 5 min | Cached tenant config JSON |
| `hist:<tenant_id>:<sender_id>` | 24 h | List of last 50 turn dicts (LPUSH/LRANGE) |
| `mq:default` | – | RQ default queue |
| `mq:ingest` | – | RQ ingestion queue |
| `mq:high` | – | Latency-sensitive jobs |
| `rl:<tenant_id>:msg_min` | 60 s | Sliding-window message-rate counter |
| `rl:<tenant_id>:tokens_day` | 24 h | LM token counter |
| `dedup:<tenant_id>:<channel>:<msg_id>` | 7 d | Idempotency mirror |
| `processing:<tenant_id>:<sender_id>` | 30 s | Concurrency guard so one user's messages are processed in order |

Eviction: `allkeys-lru`. Memory budget for pilot: 256 MB.

---

## 7. Migration Strategy

### 7.1 Tooling

- **Alembic** for SQL migrations. Auto-generated from SQLAlchemy / SQLModel models, hand-edited where necessary.
- A small **vector-migration script** maintained alongside — `migrate_v1_to_v2.py` that loops every tenant collection and applies any schema change. Vector DBs do not have migration frameworks; we own this.

### 7.2 Workflow

1. PR introduces a SQL migration under `migrations/postgres/<timestamp>_<name>.py`.
2. CI runs the migration against a fresh Postgres + an upgrade test.
3. Deployments execute pending migrations before booting workers / API.
4. Down-migrations are written but only auto-applied in dev (in prod, rollback uses a backup restore).

### 7.3 Schema additions vs breaking changes

- **Additive:** new column with a default → safe to deploy without coordinating.
- **Breaking:** rename / drop / type change → split into 3 deploys: add new, dual-write, switch reads, drop old.

---

## 8. Backup, Retention, and Erasure

### 8.1 Backup

| Asset | Frequency | Method | Retention |
|---|---|---|---|
| Postgres | Daily | `pg_dump` → R2 | 14 days |
| Postgres | Continuous | WAL streaming (if Render Postgres plan allows) | – |
| Milvus volume | Weekly | tar of `db/` dir → R2 | 30 days |
| R2 bucket | Continuous | R2 native versioning | 30 days |
| Audit-record archive | Daily | export to `tenants/<id>/audit/<date>.jsonl.gz` | 1 year |

### 8.2 Retention

- Conversation transcripts: **90 days** by default (configurable per tenant).
- Audit records: 1 year (research artefact).
- Feedback corrections: indefinite (they are tenant-owned canonical answers).
- Raw uploads: indefinite while document is `ready`; deleted within 7 days of `archived`.

### 8.3 Right-to-erasure ("forget me")

A customer keyword (e.g. typing `forget me`) triggers an erasure job:

1. Hard-delete all `turns` for `(tenant_id, sender_id)`.
2. Hard-delete all `audit_records` linked to those `turn_ids`.
3. Drop the conversation row.
4. Notify SME owner via dashboard.

Tenant-side erasure (a tenant offboarding) cascades: all rows deleted, vector collection dropped, R2 prefix purged, WhatsApp creds revoked.

---

## 9. Tenant Provisioning Procedure

When a new tenant signs up:

```python
def provision(business_name: str, slug: str, owner_user_id: UUID) -> UUID:
    with db.transaction() as tx:
        tenant_id = tx.fetchval(
            "INSERT INTO tenants (business_name, slug) VALUES (%s, %s) RETURNING tenant_id",
            (business_name, slug),
        )
        tx.execute(
            "INSERT INTO tenant_memberships (tenant_id, user_id, role) "
            "VALUES (%s, %s, 'owner')",
            (tenant_id, owner_user_id),
        )

        default_cfg = {
            "tenant_id": str(tenant_id),
            "business_name": business_name,
            "tagline": "",
            "tone": "casual",
            "languages": ["en", "pid"],
            "timezone": "Africa/Lagos",
            "operating_hours": {"mon_fri": "09:00-19:00", "sat": "10:00-17:00", "sun": "closed"},
            "greeting": f"Hi! Welcome to {business_name}. How can I help you today?",
            "out_of_hours": "Thanks for reaching out — we're closed for now. We'll reply when we're back.",
            "fallback": "I'm not sure about that one — let me get a human colleague to help.",
            "escalation_rules": [],
            "brand_voice_examples": [],
            "retrieval_weights": {"manual_faq": 4, "faq": 3, "pricing": 2, "catalogue": 2, "policy": 1},
            "version": 1,
        }
        tx.execute(
            "INSERT INTO tenant_configs (tenant_id, version, data, edited_by) "
            "VALUES (%s, 1, %s, %s)",
            (tenant_id, json.dumps(default_cfg), owner_user_id),
        )

        widget_key = f"pk_live_{secrets.token_urlsafe(32)}"
        tx.execute(
            "INSERT INTO tenant_widget_keys (widget_key, tenant_id, allowed_origins) "
            "VALUES (%s, %s, '{}')",
            (widget_key, tenant_id),
        )

    # Outside the SQL transaction: create vector collection (idempotent).
    vector_admin.ensure_collection(f"kb_{tenant_id.hex[:12]}")

    return tenant_id
```

The procedure is idempotent on retry: the SQL is wrapped in a transaction; vector collection creation is separately idempotent.
