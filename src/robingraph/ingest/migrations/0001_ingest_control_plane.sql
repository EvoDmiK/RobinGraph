CREATE TABLE source_dataset (
    id text PRIMARY KEY,
    source_id text NOT NULL,
    name text NOT NULL,
    provider text NOT NULL,
    landing_uri text NOT NULL,
    release_strategy text NOT NULL CHECK (release_strategy IN ('versioned', 'dated_snapshot', 'mutable')),
    policy_status text NOT NULL CHECK (policy_status IN ('allowed', 'restricted', 'review_required', 'denied')),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE source_release (
    id text PRIMARY KEY,
    dataset_id text NOT NULL REFERENCES source_dataset(id),
    release_key text NOT NULL,
    content_sha256 char(64),
    raw_object_uri text,
    retrieved_at timestamptz NOT NULL,
    status text NOT NULL DEFAULT 'staging'
        CHECK (status IN ('staging', 'active', 'superseded', 'failed')),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (dataset_id, release_key),
    CHECK (content_sha256 IS NULL OR content_sha256 ~ '^[0-9a-f]{64}$')
);

CREATE TABLE ingestion_run (
    id text PRIMARY KEY,
    pipeline_id text NOT NULL,
    source_release_id text REFERENCES source_release(id),
    status text NOT NULL CHECK (status IN ('pending', 'loading', 'succeeded', 'failed')),
    pipeline_git_sha text,
    config_sha256 char(64),
    started_at timestamptz NOT NULL,
    finished_at timestamptz,
    manifest jsonb NOT NULL DEFAULT '{}'::jsonb,
    counts jsonb NOT NULL DEFAULT '{}'::jsonb,
    error_reason text,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (config_sha256 IS NULL OR config_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (finished_at IS NULL OR finished_at >= started_at),
    CHECK (status NOT IN ('succeeded', 'failed') OR finished_at IS NOT NULL)
);

CREATE TABLE source_record (
    id text PRIMARY KEY,
    source_release_id text NOT NULL REFERENCES source_release(id),
    external_id text NOT NULL,
    record_type text NOT NULL,
    record_version text NOT NULL DEFAULT '1',
    supersedes_record_id text REFERENCES source_record(id),
    raw_object_uri text NOT NULL,
    raw_sha256 char(64) NOT NULL CHECK (raw_sha256 ~ '^[0-9a-f]{64}$'),
    retrieved_at timestamptz NOT NULL,
    source_updated_at timestamptz,
    parser_version text NOT NULL,
    ingestion_run_id text NOT NULL REFERENCES ingestion_run(id),
    license_policy_status text NOT NULL
        CHECK (license_policy_status IN ('allowed', 'restricted', 'review_required', 'denied')),
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source_release_id, external_id, record_version),
    CHECK (supersedes_record_id IS NULL OR supersedes_record_id <> id)
);

CREATE TABLE quarantine_item (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    record_key text NOT NULL,
    ingestion_run_id text NOT NULL REFERENCES ingestion_run(id),
    stage text NOT NULL CHECK (stage IN ('fetch', 'parse', 'validate', 'resolve', 'dedupe', 'load', 'embed', 'project')),
    reason_code text NOT NULL,
    severity text NOT NULL CHECK (severity IN ('warning', 'error', 'blocked')),
    field_path text,
    raw_value_redacted jsonb,
    rule_version text NOT NULL,
    first_seen_run_id text NOT NULL REFERENCES ingestion_run(id),
    last_seen_run_id text NOT NULL REFERENCES ingestion_run(id),
    resolution_status text NOT NULL DEFAULT 'open'
        CHECK (resolution_status IN ('open', 'ignored', 'fixed', 'source_fixed')),
    first_seen_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (last_seen_at >= first_seen_at)
);

CREATE UNIQUE INDEX quarantine_item_identity
    ON quarantine_item (record_key, stage, reason_code, COALESCE(field_path, ''));

CREATE TABLE ingest_state (
    pipeline_id text PRIMARY KEY,
    active_release_id text REFERENCES source_release(id),
    last_successful_run_id text REFERENCES ingestion_run(id),
    cursor jsonb NOT NULL DEFAULT '{}'::jsonb,
    version bigint NOT NULL DEFAULT 0 CHECK (version >= 0),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE outbox_event (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_key text NOT NULL UNIQUE,
    aggregate_type text NOT NULL,
    aggregate_id text NOT NULL,
    event_type text NOT NULL,
    payload jsonb NOT NULL,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    available_at timestamptz NOT NULL DEFAULT now(),
    claimed_at timestamptz,
    claimed_by text,
    published_at timestamptz,
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    last_error text,
    CHECK ((claimed_at IS NULL) = (claimed_by IS NULL))
);

CREATE INDEX source_record_release_type_idx
    ON source_record (source_release_id, record_type);
CREATE INDEX source_record_run_idx
    ON source_record (ingestion_run_id);
CREATE INDEX quarantine_item_open_idx
    ON quarantine_item (ingestion_run_id, severity)
    WHERE resolution_status = 'open';
CREATE INDEX outbox_event_ready_idx
    ON outbox_event (available_at, id)
    WHERE published_at IS NULL;
