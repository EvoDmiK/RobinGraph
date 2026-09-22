ALTER TABLE outbox_event
    ADD COLUMN claim_token uuid,
    ADD COLUMN dead_lettered_at timestamptz,
    ADD CONSTRAINT outbox_event_claim_token_check
        CHECK ((claimed_at IS NULL) = (claim_token IS NULL)),
    ADD CONSTRAINT outbox_event_terminal_state_check
        CHECK (published_at IS NULL OR dead_lettered_at IS NULL);

DROP INDEX outbox_event_ready_idx;

CREATE INDEX outbox_event_ready_idx
    ON outbox_event (available_at, id)
    WHERE published_at IS NULL AND dead_lettered_at IS NULL;
