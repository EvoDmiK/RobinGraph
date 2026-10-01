ALTER TABLE outbox_event
    ADD COLUMN ingestion_run_id text NOT NULL REFERENCES ingestion_run(id);

CREATE INDEX outbox_event_run_idx
    ON outbox_event (ingestion_run_id, id);

CREATE INDEX ingestion_run_loading_idx
    ON ingestion_run (started_at)
    WHERE status = 'loading';

CREATE INDEX ingestion_run_pipeline_started_idx
    ON ingestion_run (pipeline_id, started_at DESC);
