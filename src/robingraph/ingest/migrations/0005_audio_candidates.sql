CREATE TABLE audio_recording_candidate (
    id text PRIMARY KEY,
    scientific_name text NOT NULL,
    file_title text NOT NULL,
    status text NOT NULL CHECK (status IN ('awaiting_review', 'approved', 'published', 'rejected', 'deferred')),
    data jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (scientific_name, file_title)
);
CREATE INDEX audio_recording_published_species_idx
    ON audio_recording_candidate (scientific_name) WHERE status = 'published';
