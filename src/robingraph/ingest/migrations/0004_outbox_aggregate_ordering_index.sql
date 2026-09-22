CREATE INDEX outbox_event_aggregate_unpublished_idx
    ON outbox_event (aggregate_type, aggregate_id, id)
    WHERE published_at IS NULL;
