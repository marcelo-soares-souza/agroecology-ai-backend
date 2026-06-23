ALTER TABLE academic_metadata_runs
    DROP CONSTRAINT IF EXISTS academic_metadata_runs_delay_seconds_check;

ALTER TABLE academic_metadata_runs
    ADD CONSTRAINT academic_metadata_runs_delay_seconds_check
    CHECK (delay_seconds >= 1);
