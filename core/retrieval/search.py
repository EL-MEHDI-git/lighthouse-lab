"""
Point d'entrée de la recherche.

Choisit la stratégie (hybride ou dense seule) selon `HYBRID_ENABLED`
et formate le contexte envoyé au LLM.

    search(query)  → liste de chunks (une seule requête, une seule fois)
"""
from typing import Optional

from core.config import HYBRID_ENABLED, TOP_K, MAX_CONTEXT_LENGTH
from core.retrieval.hybrid_search import hybrid_search
from core.retrieval.vector_search import vector_search


def search(query: str, top_k: int = TOP_K, domain: Optional[str] = None) -> list[dict]:
    """Recherche les chunks les plus pertinents (hybride ou dense)."""
    if HYBRID_ENABLED:
        return hybrid_search(query, top_k, domain)
    return vector_search(query, top_k, domain)


def build_context(results: list[dict], max_length: int = MAX_CONTEXT_LENGTH) -> str:
    """Formate les chunks récupérés en contexte pour le LLM."""
    if not results:
        return "Aucun contexte pertinent trouvé."

    parts = []
    current_length = 0

    for result in results:
        chunk_text = (
            f"Source: {result['source']}\n"
            f"Domaine: {result['domain']}\n"
            f"Contenu: {result['content']}\n"
            f"Similarité: {result['similarity']:.2f}"
        )

        if current_length + len(chunk_text) > max_length:
            break

        parts.append(chunk_text)
        current_length += len(chunk_text)

    return "\n\n---\n\n".join(parts)


def get_context_for_query(
    query: str,
    top_k: int = TOP_K,
    max_length: int = MAX_CONTEXT_LENGTH,
    domain: Optional[str] = None,
) -> str:
    """Raccourci : recherche + formatage du contexte en un appel."""
    return build_context(search(query, top_k, domain), max_length)
