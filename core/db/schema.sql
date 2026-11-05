-- core/db/schema.sql
CREATE EXTENSION IF NOT EXISTS vector;


CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    domain TEXT NOT NULL,
    source TEXT,
    chunk_index INT,
    content TEXT,
    embedding VECTOR(1024)
);
