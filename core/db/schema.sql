-- core/db/schema.sql
-- Exécuté automatiquement par PostgreSQL au premier démarrage (volume vide).

CREATE EXTENSION IF NOT EXISTS vector;


CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    domain TEXT NOT NULL,
    source TEXT,
    chunk_index INT,
    content TEXT,
    embedding VECTOR(1024),
    -- Colonne générée pour le full-text search (hybrid search).
    -- 'english' = stemming anglais ; le corpus Anthropic est en anglais.
    content_tsv TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', content)) STORED
);

-- Recherche lexicale (full-text) : indispensable pour le hybrid search.
CREATE INDEX IF NOT EXISTS documents_content_tsv_idx
    ON documents USING GIN (content_tsv);

-- Filtrage par domaine (utilisé par toutes les requêtes de retrieval).
CREATE INDEX IF NOT EXISTS documents_domain_idx
    ON documents (domain);
