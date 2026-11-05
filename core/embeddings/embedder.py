from sentence_transformers import SentenceTransformer
import torch

from core.config import (
    EMBEDDING_MODEL_NAME,
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_NORMALIZE,
    EMBEDDING_MAX_SEQ_LENGTH,
)

_model = None

# GPU Apple (MPS) si disponible, sinon CPU
_DEVICE = "mps" if torch.backends.mps.is_available() else "cpu"


def get_model(model_name: str = EMBEDDING_MODEL_NAME) -> SentenceTransformer:
    """Retourne le modèle d'embedding (chargé paresseusement)."""
    global _model
    if _model is None:
        _model = SentenceTransformer(model_name, device=_DEVICE)
        _model.max_seq_length = EMBEDDING_MAX_SEQ_LENGTH
    return _model


def embed_text(text: str, model_name: str = EMBEDDING_MODEL_NAME) -> list[float]:
    """Génère l'embedding vectoriel d'un texte."""
    model = get_model(model_name)
    return model.encode(text, normalize_embeddings=EMBEDDING_NORMALIZE).tolist()


def embed_batch(
    texts: list[str],
    model_name: str = EMBEDDING_MODEL_NAME,
    batch_size: int = EMBEDDING_BATCH_SIZE,
    show_progress: bool = False
) -> list[list[float]]:
    """Génère les embeddings pour plusieurs textes (plus rapide)."""
    model = get_model(model_name)
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=EMBEDDING_NORMALIZE,
        show_progress_bar=show_progress
    )
    return embeddings.tolist()


def get_embedding_dimension(model_name: str = EMBEDDING_MODEL_NAME) -> int:
    """Retourne la dimension des embeddings du modèle."""
    model = get_model(model_name)
    return model.get_embedding_dimension()
