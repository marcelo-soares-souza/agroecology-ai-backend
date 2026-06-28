-- documents: /api/v1/documents ranks agroecology-related title variants first.
DROP INDEX IF EXISTS idx_documents_agroecology_title_priority;

CREATE INDEX idx_documents_agroecology_title_priority
    ON documents (
        (
            CASE
                WHEN POSITION('agroecolog' IN LOWER(COALESCE(title, ''))) > 0
                THEN 0
                ELSE 1
            END
        ),
        title ASC NULLS LAST,
        filename ASC,
        created_at DESC,
        id
    );
