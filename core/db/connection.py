import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
from typing import Optional
from core.config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD


def get_connection():
    """Établit une connexion à la base de données PostgreSQL."""
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def insert_chunk(
    conn, 
    domain: str,
    source: str, 
    chunk_index: int,
    content: str, 
    embedding: list[float]
) -> int:
    """Insère un chunk avec son embedding dans la base de données."""
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO documents (domain, source, chunk_index, content, embedding) 
               VALUES (%s, %s, %s, %s, %s) 
               RETURNING id""",
            (domain, source, chunk_index, content, embedding)
        )
        return cur.fetchone()[0]


def insert_chunks_batch(
    conn,
    chunks: list[dict],
    embeddings: list[list[float]]
) -> list[int]:
    """Insère plusieurs chunks en une seule requête (plus rapide)."""
    values = [
        (chunk["domain"], chunk["source"], chunk["chunk_index"], chunk["content"], emb)
        for chunk, emb in zip(chunks, embeddings)
    ]

    # execute_values supporte RETURNING et renvoie les IDs insérés
    with conn.cursor() as cur:
        query = """
            INSERT INTO documents (domain, source, chunk_index, content, embedding)
            VALUES %s
            RETURNING id
        """
        rows = execute_values(cur, query, values, fetch=True)
        return [row[0] for row in rows]


def get_ingested_sources(conn, domain: str) -> set[str]:
    """Retourne les sources déjà ingérées pour un domaine donné."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT source FROM documents WHERE domain = %s",
            (domain,)
        )
        return {row[0] for row in cur.fetchall()}


def search_similar(
    conn,
    query_embedding: list[float],
    top_k: int = 5,
    domain: Optional[str] = None,
    include_embedding: bool = False
) -> list[dict]:
    """Recherche les chunks les plus similaires par cosine similarity."""
    embedding_column = ", embedding" if include_embedding else ""
    where_clause = "WHERE domain = %s" if domain else ""

    sql = f"""
        SELECT id, domain, source, chunk_index, content,
               1 - (embedding <=> %s::vector) AS similarity
               {embedding_column}
        FROM documents
        {where_clause}
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """

    params = [query_embedding]
    if domain:
        params.append(domain)
    params.extend([query_embedding, top_k])

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def search_lexical(
    conn,
    query: str,
    top_k: int = 40,
    domain: Optional[str] = None
) -> list[dict]:
    """
    Recherche lexicale (full-text PostgreSQL) sur `content_tsv`.

    Utilise `websearch_to_tsquery` qui accepte une saisie libre
    (mots, "expression exacte", OR, -exclusion) sans jamais lever d'erreur.
    """
    where_clause = "AND domain = %s" if domain else ""

    sql = f"""
        SELECT id, domain, source, chunk_index, content,
               ts_rank_cd(content_tsv, websearch_to_tsquery('english', %s)) AS lexical_score
        FROM documents
        WHERE content_tsv @@ websearch_to_tsquery('english', %s)
        {where_clause}
        ORDER BY lexical_score DESC
        LIMIT %s
    """

    params = [query, query]
    if domain:
        params.append(domain)
    params.append(top_k)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def get_chunks_with_embeddings(conn, ids: list[int]) -> list[dict]:
    """Récupère des chunks (avec leur embedding) par identifiant."""
    if not ids:
        return []

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """SELECT id, domain, source, chunk_index, content, embedding
               FROM documents
               WHERE id = ANY(%s)""",
            (ids,)
        )
        return cur.fetchall()
