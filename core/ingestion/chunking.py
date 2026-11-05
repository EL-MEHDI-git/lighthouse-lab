"""
Découpage intelligent des documents Markdown.

Stratégie :
1. Découper aux titres Markdown (H1/H2/H3) → chunks sémantiquement cohérents.
2. Re-découper les sections trop longues avec un splitter récursif.
3. Filtrer les chunks trop courts (bruit).
4. Dédupliquer les chunks identiques dans un même document.
"""
import hashlib

from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from core.config import CHUNK_SIZE, CHUNK_OVERLAP, MIN_CHUNK_LENGTH

HEADERS_TO_SPLIT_ON = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
]


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Découpe un texte brut en chunks avec chevauchement (fallback générique)."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_text(text)


def chunk_documents(
    documents: list[dict],
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
    min_length: int = MIN_CHUNK_LENGTH,
) -> list[dict]:
    """Découpe une liste de documents Markdown en chunks propres."""
    md_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=HEADERS_TO_SPLIT_ON,
        strip_headers=False,  # garder les titres dans le texte (utile pour le retrieval)
    )
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunked_docs = []

    for doc in documents:
        sections = md_splitter.split_text(doc["content"])

        pieces: list[str] = []
        for section in sections:
            text = section.page_content.strip()
            if not text:
                continue
            if len(text) > chunk_size:
                pieces.extend(text_splitter.split_text(text))
            else:
                pieces.append(text)

        seen_hashes: set[str] = set()
        chunk_index = 0

        for piece in pieces:
            content = piece.strip()
            if len(content) < min_length:
                continue

            content_hash = hashlib.md5(content.encode("utf-8")).hexdigest()
            if content_hash in seen_hashes:
                continue
            seen_hashes.add(content_hash)

            chunked_docs.append({
                "domain": doc["domain"],
                "source": doc["source"],
                "chunk_index": chunk_index,
                "content": content,
            })
            chunk_index += 1

    return chunked_docs
