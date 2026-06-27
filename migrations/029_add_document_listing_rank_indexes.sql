-- documents: /api/v1/documents ranks titles containing "agroecology" first.
CREATE INDEX IF NOT EXISTS idx_documents_agroecology_title_priority
    ON documents (
        (
            CASE
                WHEN POSITION('agroecology' IN LOWER(COALESCE(title, ''))) > 0
                THEN 0
                ELSE 1
            END
        ),
        title ASC NULLS LAST,
        filename ASC,
        created_at DESC,
        id
    );

-- document_academic_metadata: /api/v1/documents ranks by citations, then references.
CREATE INDEX IF NOT EXISTS idx_document_academic_metadata_citation_reference_document
    ON document_academic_metadata (
        citation_count DESC NULLS LAST,
        reference_count DESC NULLS LAST,
        document_id
    );
