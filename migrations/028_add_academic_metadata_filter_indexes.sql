-- document_academic_metadata: /api/v1/documents publication_year filter.
CREATE INDEX IF NOT EXISTS idx_document_academic_metadata_publication_year_document
    ON document_academic_metadata (publication_year, document_id)
    WHERE publication_year IS NOT NULL;

-- document_academic_metadata: /api/v1/documents full_metadata filter.
CREATE INDEX IF NOT EXISTS idx_document_academic_metadata_complete_document
    ON document_academic_metadata (document_id)
    WHERE publication_year IS NOT NULL
      AND citation_count IS NOT NULL
      AND NULLIF(BTRIM(COALESCE(source_url, '')), '') IS NOT NULL;

-- documents: academic metadata eligibility checks and ordered full_metadata listing.
CREATE INDEX IF NOT EXISTS idx_documents_academic_metadata_eligible_order
    ON documents (title ASC NULLS LAST, filename ASC, created_at DESC, id)
    WHERE NULLIF(BTRIM(COALESCE(title, '')), '') IS NOT NULL
      AND NULLIF(BTRIM(COALESCE(authors, '')), '') IS NOT NULL;

-- academic_metadata_runs: latest-run status lookup.
CREATE INDEX IF NOT EXISTS idx_academic_metadata_runs_created_at
    ON academic_metadata_runs (created_at DESC);
