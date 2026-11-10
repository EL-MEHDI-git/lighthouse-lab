"""
Reranker cross-encoder.

Contrairement aux embeddings (bi-encoder), le cross-encoder lit la question ET le
chunk **ensemble** : il juge la pertinence réelle, pas une proximité de vecteurs.
C'est plus lent (1 forward par candidat) mais bien plus précis — d'où son usage
en dernière étape, sur un petit pool déjà filtré.
"""
import numpy as np
import torch
from sentence_transformers import CrossEncoder

from core.config import RERANK_MODEL

_model = None

_DEVICE = "mps" if torch.backends.mps.is_available() else "cpu"


def get_model(model_name: str = RERANK_MODEL) -> CrossEncoder:
    """Retourne le cross-encoder (chargé paresseusement)."""
    global _model
    if _model is None:
        _model = CrossEncoder(model_name, max_length=512, device=_DEVICE)
    return _model


def rerank(
    query: str,
    candidates: list[dict],
    top_k: int | None = None,
    model_name: str = RERANK_MODEL,
) -> list[dict]:
    """
    Re-trie des candidats selon leur pertinence réelle pour la requête.

    Ajoute une clé `rerank_score` ∈ [0, 1] (sigmoid du logit) et trie par ordre
    décroissant. Les autres clés (dont `embedding`) sont conservées.

    Args:
        query: Question posée
        candidates: Chunks issus de la fusion RRF
        top_k: Ne garder que les N premiers (None = tous)
    """
    if not candidates:
        return []

    model = get_model(model_name)
    pairs = [(query, candidate["content"]) for candidate in candidates]
    logits = model.predict(pairs, show_progress_bar=False)

    # Sigmoid : ramène les logits dans [0, 1] pour que MMR puisse les comparer
    # à une similarité cosine.
    scores = 1.0 / (1.0 + np.exp(-np.asarray(logits, dtype=np.float32)))

    reranked = []
    for candidate, score in zip(candidates, scores):
        item = dict(candidate)
        item["rerank_score"] = float(score)
        reranked.append(item)

    reranked.sort(key=lambda item: item["rerank_score"], reverse=True)
    return reranked[:top_k] if top_k else reranked
