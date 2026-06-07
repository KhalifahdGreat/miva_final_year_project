-- =========================================================================
-- Migration 002 — durable object storage reference for uploaded documents
-- =========================================================================
-- Stores the Cloudflare R2 (S3) object key for each uploaded document so the
-- original file can be re-downloaded / re-ingested. Idempotent.

ALTER TABLE documents ADD COLUMN IF NOT EXISTS object_key TEXT;
