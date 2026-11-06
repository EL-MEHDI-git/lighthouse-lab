"""
Recherche hybride : dense (pgvector) + lexical (PostgreSQL full-text),
fusionnés par Reciprocal Rank Fusion (RRF).

Pourquoi RRF plutôt qu'une somme pondérée de scores ?
- Les scores n'ont pas la même échelle (cosine ∈ [-1, 1], ts_rank ∈ [0, ~1] mais
  distribution très différente) : les additionner demande une normalisation fragile.
- RRF ne regarde que les RANGS, jamais les scores → robuste, zéro réglage.

    score(d) = Σ  1 / (k + rang_i(d))        avec k = 60
"""
from typing import Optional

from core.config import (
    TOP_K,
    RETRIEVAL_CANDIDATES,
    LEXICAL_CANDIDATES,
    RRF_K,
    LEXICAL_WEIGHT,
)
from core.db.connection import (
    get_connection,
    search_similar,
    search_lexical,
    get_chunks_with_embeddings,
)
from core.embeddings.embedder import embed_text
from core.retrieval.vector_search import _mmr


def reciprocal_rank_fusion(
    rankings: list[list[dict]],
    k: int = RRF_K,
    weights: Optional[list[float]] = None,
) -> list[dict]:
    """
    Fusionne plusieurs classements en un seul, par rang (RRF).

    Args:
        rankings: liste de classements (chacun trié du plus pertinent au moins pertinent)
        k: constante RRF (60 par défaut)
        weights: poids par classement, même ordre que `rankings`
    """
    if weights is None:
        weights = [1.0] * len(rankings)

    scores: dict[int, float] = {}
    items: dict[int, dict] = {}

    for ranking, weight in zip(rankings, weights):
        for rank, item in enumerate(ranking, start=1):
            doc_id = item["id"]
            scores[doc_id] = scores.get(doc_id, 0.0) + weight / (k + rank)
            items.setdefault(doc_id, dict(item))

    return [
        {**items[doc_id], "rrf_score": score}
        for doc_id, score in sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    ]


def hybrid_search(
    query: str,
    top_k: int = TOP_K,
    domain: Optional[str] = None,
) -> list[dict]:
    """
    Recherche hybride : 40 candidats denses + 40 candidats lexicaux,
    fusion RRF, puis MMR pour la diversité des top_k finaux.

    Args:
        query: Texte de la requête
        top_k: Nombre de résultats finaux
        domain: Filtrer par domaine (optionnel)
    """
    query_embedding = embed_text(query)

    conn = get_connection()
    try:
        dense = search_similar(
            conn, query_embedding, RETRIEVAL_CANDIDATES, domain
        )
        lexical = search_lexical(conn, query, LEXICAL_CANDIDATES, domain)

        fused = reciprocal_rank_fusion(
            [dense, lexical], weights=[1.0, LEXICAL_WEIGHT]
        )
        if not fused:
            return []

        # On garde les meilleurs de la fusion, puis on récupère leurs embeddings
        # (indispensable pour le MMR).
        pool_ids = [item["id"] for item in fused[:RETRIEVAL_CANDIDATES]]
        candidates = get_chunks_with_embeddings(conn, pool_ids)

        # Réordonner selon l'ordre de la fusion
        order = {doc_id: position for position, doc_id in enumerate(pool_ids)}
        candidates.sort(key=lambda c: order[c["id"]])

        # Conserver le score RRF dans les résultats finaux
        rrf_scores = {item["id"]: item["rrf_score"] for item in fused}
        for candidate in candidates:
            candidate["rrf_score"] = rrf_scores[candidate["id"]]

        # MMR avec le score RRF comme pertinence : sans ça, un chunk trouvé
        # uniquement par le lexical serait éliminé par son cosine moyen.
        relevance = [candidate["rrf_score"] for candidate in candidates]
        return _mmr(query_embedding, candidates, top_k, relevance=relevance)
    finally:
        conn.close()
