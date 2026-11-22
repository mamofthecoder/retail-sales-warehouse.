CREATE INDEX sales_load_runs_succeeded_batch_idx
ON sales_load_runs (batch_id)
WHERE status = 'succeeded';
