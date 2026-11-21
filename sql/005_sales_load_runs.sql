CREATE TABLE sales_load_runs (
    run_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    batch_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'succeeded', 'failed')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    finished_at TIMESTAMPTZ,
    error_message TEXT,
    staged_line_count BIGINT CHECK (staged_line_count >= 0),
    fact_rows_changed BIGINT CHECK (fact_rows_changed >= 0),
    rejection_rows_changed BIGINT CHECK (rejection_rows_changed >= 0),
    rejections_resolved BIGINT CHECK (rejections_resolved >= 0)
);
