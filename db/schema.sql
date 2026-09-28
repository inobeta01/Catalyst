-- Enable required extension for gen_random_uuid()
-- Note: Creating extensions requires superuser privileges. If the database role
-- executing this schema lacks permission, ensure pgcrypto is pre-installed or
-- use an alternative UUID generation method (e.g., uuid-ossp or application-layer).
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ============================================================
-- Failure mode catalog (from failure-modes/*.yaml)
-- Must be created first because other tables reference it
-- ============================================================
CREATE TABLE IF NOT EXISTS failure_modes (
    id                  TEXT        PRIMARY KEY,
    description         TEXT        NOT NULL,
    agent_name          TEXT        NOT NULL,
    perturbation_fn     TEXT        NOT NULL,
    perturbation_args   JSONB       NOT NULL DEFAULT '{}',
    fixture_path        TEXT        NOT NULL,
    expected_perturbed  JSONB       NOT NULL,
    expected_control    JSONB       NOT NULL,
    realism_bar         TEXT,
    active              BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- Top-level run context
-- ============================================================
CREATE TABLE IF NOT EXISTS runs (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id              TEXT        NOT NULL UNIQUE,
    run_type            TEXT        NOT NULL,           -- 'eval' | 'single' | 'smoke'
    failure_mode_tag    TEXT,
    agent_name          TEXT        NOT NULL,
    fixture_path        TEXT        NOT NULL,
    perturbation_id     UUID,
    status              TEXT        NOT NULL DEFAULT 'pending',
    started_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at        TIMESTAMPTZ,
    duration_ms         INTEGER,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_runs_run_id           ON runs (run_id);
CREATE INDEX IF NOT EXISTS idx_runs_agent_name       ON runs (agent_name);
CREATE INDEX IF NOT EXISTS idx_runs_failure_mode_tag ON runs (failure_mode_tag);

-- ============================================================
-- What was intentionally broken per run
-- ============================================================
CREATE TABLE IF NOT EXISTS perturbations (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id              TEXT        NOT NULL REFERENCES runs (run_id) ON DELETE CASCADE,
    failure_mode_id     TEXT        NOT NULL REFERENCES failure_modes (id),
    perturbation_fn     TEXT        NOT NULL,
    args_applied        JSONB       NOT NULL DEFAULT '{}',
    applied_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_perturbations_run_id          ON perturbations (run_id);
CREATE INDEX IF NOT EXISTS idx_perturbations_failure_mode_id ON perturbations (failure_mode_id);

-- ============================================================
-- Batch eval reports
-- ============================================================
CREATE TABLE IF NOT EXISTS eval_results (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    eval_batch_id       TEXT        NOT NULL UNIQUE,
    total_modes         INTEGER     NOT NULL,
    passed              INTEGER     NOT NULL DEFAULT 0,
    regressed           INTEGER     NOT NULL DEFAULT 0,
    infra_errors        INTEGER     NOT NULL DEFAULT 0,
    noise_flagged       INTEGER     NOT NULL DEFAULT 0,
    duration_ms         INTEGER,
    exit_code           INTEGER     NOT NULL,
    report_json         JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- Per-failure-mode breakdown within a batch
-- ============================================================
CREATE TABLE IF NOT EXISTS eval_result_rows (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    eval_batch_id       TEXT        NOT NULL REFERENCES eval_results (eval_batch_id) ON DELETE CASCADE,
    failure_mode_id     TEXT        NOT NULL REFERENCES failure_modes (id),
    perturbed_run_id    TEXT        REFERENCES runs (run_id),
    control_run_id      TEXT        REFERENCES runs (run_id),
    perturbed_result    TEXT        NOT NULL,
    control_result      TEXT        NOT NULL,
    duration_ms         INTEGER,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_eval_result_rows_batch_id        ON eval_result_rows (eval_batch_id);
CREATE INDEX IF NOT EXISTS idx_eval_result_rows_failure_mode_id ON eval_result_rows (failure_mode_id);

-- ============================================================
-- Tool response record/replay for deterministic control runs
-- ============================================================
CREATE TABLE IF NOT EXISTS replay_cache (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    cache_key           TEXT        NOT NULL UNIQUE,   -- SHA-256(tool_name + input_json)
    tool_name           TEXT        NOT NULL,
    input_json          JSONB       NOT NULL,
    output_json         JSONB       NOT NULL,
    recorded_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    hit_count           INTEGER     NOT NULL DEFAULT 0,
    last_hit_at         TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_replay_cache_cache_key ON replay_cache (cache_key);
CREATE INDEX IF NOT EXISTS idx_replay_cache_tool_name ON replay_cache (tool_name);

-- ============================================================
-- Internal doc index for corpus/sanitized/
-- ============================================================
CREATE TABLE IF NOT EXISTS knowledge_base (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id              TEXT        NOT NULL UNIQUE,
    agent_scope         TEXT,
    file_path           TEXT        NOT NULL,
    title               TEXT,
    content_hash        TEXT        NOT NULL,
    chunk_count         INTEGER,
    redacted            BOOLEAN     NOT NULL DEFAULT TRUE,
    indexed_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_knowledge_base_agent_scope ON knowledge_base (agent_scope);

-- ============================================================
-- Versioned prompt history (required for prompt-drift failure mode)
-- ============================================================
CREATE TABLE IF NOT EXISTS prompt_versions (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name          TEXT        NOT NULL,
    prompt_key          TEXT        NOT NULL,
    version             INTEGER     NOT NULL,
    content             TEXT        NOT NULL,
    is_current          BOOLEAN     NOT NULL DEFAULT FALSE,
    committed_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (agent_name, prompt_key, version)
);

CREATE INDEX IF NOT EXISTS idx_prompt_versions_agent_name ON prompt_versions (agent_name);
CREATE INDEX IF NOT EXISTS idx_prompt_versions_is_current ON prompt_versions (is_current);