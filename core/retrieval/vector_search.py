"""
Module de recherche vectorielle avec pgvector.

Stratégie :
1. Récupérer un large pool de candidats par similarité cosine (pgvector).
2. Réordonner avec MMR (Maximal Marginal Relevance) pour éviter de renvoyer
   plusieurs chunks quasi identiques et améliorer la diversité.
"""
from typing import Optional

import numpy as np

from core.config import TOP_K, RETRIEVAL_CANDIDATES, MMR_LAMBDA
from core.db.connection import get_connection, search_similar
from core.embeddings.embedder import embed_text


def _to_array(vector) -> np.ndarray:
    """Convertit un vecteur (liste ou string pgvector) en array numpy."""
    if isinstance(vector, str):
        return np.fromstring(vector.strip().strip("[]"), sep=",", dtype=np.float32)
    return np.asarray(vector, dtype=np.float32)


def _normalize(vector: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vector)
    return vector / norm if norm > 0 else vector


def _mmr(
    query_embedding: list[float],
    candidates: list[dict],
    top_k: int,
    lam: float = MMR_LAMBDA,
    relevance: Optional[list[float]] = None
) -> list[dict]:
    """
    Sélectionne top_k candidats diversifiés via Maximal Marginal Relevance.

    Args:
        relevance: signal de pertinence à utiliser (ex. score RRF d'une fusion
            hybride). Par défaut : similarité cosine avec la requête.
            Le cosine sert toujours à mesurer la redondance entre candidats.
    """
    if not candidates:
        return []

    query = _normalize(_to_array(query_embedding))
    matrix = np.vstack([_normalize(_to_array(c["embedding"])) for c in candidates])
    similarities = matrix @ query

    if relevance is None:
        relevance_scores = similarities
    else:
        relevance_scores = np.asarray(relevance, dtype=np.float32)
        highest = float(relevance_scores.max())
        if highest > 0:
            relevance_scores = relevance_scores / highest

    selected: list[int] = []
    remaining = list(range(len(candidates)))

    while remaining and len(selected) < top_k:
        if not selected:
            best = max(remaining, key=lambda i: relevance_scores[i])
        else:
            chosen = matrix[selected]
            best_score = -np.inf
            best = remaining[0]
            for i in remaining:
                redundancy = float(np.max(chosen @ matrix[i]))
                score = lam * float(relevance_scores[i]) - (1.0 - lam) * redundancy
                if score > best_score:
                    best_score = score
                    best = i

        selected.append(best)
        remaining.remove(best)

    results = []
    for i in selected:
        item = {k: v for k, v in candidates[i].items() if k != "embedding"}
        item["similarity"] = float(similarities[i])
        results.append(item)
    return results


def vector_search(
    query: str,
    top_k: int = TOP_K,
    domain: Optional[str] = None,
    use_mmr: bool = True
) -> list[dict]:
    """
    Recherche les chunks les plus pertinents pour une requête.

    Args:
        query: Texte de la requête
        top_k: Nombre de résultats finaux
        domain: Filtrer par domaine (optionnel)
        use_mmr: Diversifier les résultats (évite les doublons quasi identiques)
    """
    query_embedding = embed_text(query)

    conn = get_connection()
    try:
        if use_mmr:
            candidates = search_similar(
                conn,
                query_embedding,
                RETRIEVAL_CANDIDATES,
                domain,
                include_embedding=True,
            )
            return _mmr(query_embedding, candidates, top_k)
        return search_similar(conn, query_embedding, top_k, domain)
    finally:
        conn.close()
