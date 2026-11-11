"""
Configuration centralisée du projet Lighthouse.

TOUS les paramètres modifiables du projet se trouvent ici.
Modifiez les valeurs ci-dessous et tout le système s'adapte.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# EMBEDDINGS
# =============================================================================
# Modèle d'embedding utilisé. Pour tester plusieurs modèles de benchmark,
# changez EMBEDDING_MODEL_NAME puis relancez l'ingestion (scripts/ingest.py).
EMBEDDING_MODEL_NAME = "BAAI/bge-m3"   # était all-MiniLM-L6-v2
EMBEDDING_DIMENSION = 1024             # Taille du vecteur (doit matcher le modèle)
EMBEDDING_BATCH_SIZE = 16              # Taille de lot pour embed_batch
EMBEDDING_NORMALIZE = True             # Normaliser les vecteurs (requis pour cosine)
EMBEDDING_MAX_SEQ_LENGTH = 512          # Nos chunks font ~500 chars → inutile d'aller à 8192

# =============================================================================
# INGESTION (découpage en chunks)
# =============================================================================
CHUNK_SIZE = 1000                  # Taille max d'un chunk (caractères)
CHUNK_OVERLAP = 150                # Chevauchement entre chunks
MIN_CHUNK_LENGTH = 150             # En dessous → chunk ignoré (bruit)

# =============================================================================
# BASE DE DONNÉES
# =============================================================================
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "lighthouse")
DB_USER = os.getenv("DB_USER", "lighthouse")
DB_PASSWORD = os.getenv("DB_PASSWORD", "lighthouse_password")

# Domaine par défaut pour l'ingestion / la recherche
DEFAULT_DOMAIN = "ai_engineering"

# =============================================================================
# GÉNÉRATION LLM (Ollama)
# =============================================================================
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
LLM_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
LLM_TEMPERATURE = 0.7
LLM_MAX_TOKENS = 1024

# =============================================================================
# RAG / RECHERCHE
# =============================================================================
TOP_K = 8                          # Nombre de chunks finaux renvoyés
MAX_CONTEXT_LENGTH = 4000          # Longueur max du contexte transmis au LLM
RETRIEVAL_CANDIDATES = 40          # Candidats récupérés avant MMR / rerank
MMR_LAMBDA = 0.7                   # 0 = diversité max, 1 = pertinence pure

# --- Hybrid search (dense + lexical, fusion RRF) ---
HYBRID_ENABLED = True              # False = recherche dense seule (A/B testing)
LEXICAL_CANDIDATES = 40            # Candidats renvoyés par le full-text Postgres
RRF_K = 60                         # Constante RRF (60 = valeur standard de la littérature)
LEXICAL_WEIGHT = 0.5               # Poids du lexical dans la fusion (< 1 = le dense domine)

# --- Reranker (cross-encoder) ---
# Désactivé par défaut : mesuré sur le golden set, il ne gagne rien
# (Recall@5 0.95 vs 1.00, MRR 0.82 vs 0.84) pour 5,7× plus de temps.
# Le code reste en place — repasser à True quand le golden set sera plus large.
RERANK_ENABLED = False             # False = on garde les scores RRF
RERANK_MODEL = "BAAI/bge-reranker-v2-m3"
RERANK_CANDIDATES = 40             # Candidats envoyés au cross-encoder (coût = O(n))

# =============================================================================
# MÉMOIRE DE CONVERSATION
# =============================================================================
MEMORY_MAX_HISTORY = 20            # Nombre max de messages conservés par session
MEMORY_HISTORY_IN_CONTEXT = 5      # Messages d'historique injectés dans le prompt
