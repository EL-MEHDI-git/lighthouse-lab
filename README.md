# Lighthouse Lab

AI-powered knowledge platform for illuminating information and assisting decision-making.

## Overview

Lighthouse is a RAG (Retrieval-Augmented Generation) system designed to:
- Organize knowledge across multiple domains
- Start with AI engineering news (Anthropic docs)
- Progressively evolve into a personal knowledge companion

## Tech Stack

| Brique | Choix | Pourquoi |
|---|---|---|
| Database | PostgreSQL 16 + pgvector (Docker) | Vecteurs + full-text + métadonnées dans un seul moteur |
| Embeddings | `BAAI/bge-m3` (local, 1024 dims) | Multilingue, 8192 ctx, excellent en retrieval dense |
| LLM | Ollama (`llama3.2`) | 100 % local, aucune clé API |
| Chunking | `langchain-text-splitters` (Markdown-aware) | Sections sémantiques plutôt que coupes arbitraires |
| Extraction | `trafilatura` | Supprime nav/footer/boilerplate automatiquement |

## Prerequisites

| Prérequis | Version / taille | Note |
|---|---|---|
| Docker Desktop | — | PostgreSQL + pgAdmin |
| Python | 3.11+ (testé en 3.13) | `python3 --version` |
| Ollama | — | génération locale |
| Espace disque | ~10 Go | `bge-m3` = 4,3 Go + PyTorch |
| RAM | 8 Go+ (testé sur 24 Go) | MPS sur Apple Silicon, CUDA, sinon CPU |

> **Premier lancement = long.** Le premier `ingest.py` télécharge `bge-m3` (~4,3 Go) depuis
> Hugging Face et le charge en ~2 min. Les suivants sont instantanés (cache local dans
> `~/.cache/huggingface/hub/models--BAAI--bge-m3`).

## Quick Start

### 1. Start PostgreSQL

```bash
docker compose up -d
```

> `docker-compose` (avec tiret) fonctionne aussi sur les anciennes installations.

Deux conteneurs démarrent :

| Conteneur | URL | Rôle |
|---|---|---|
| `lighthouse-db` | `localhost:5432` | PostgreSQL 16 + pgvector |
| `lighthouse-pgadmin` | http://localhost:5050 | interface web (identifiants dans `.env`) |

> **Le schéma est appliqué automatiquement**, mais **uniquement au premier démarrage**
> (volume `pgdata` vide). Voir *Database management* pour réinitialiser.

### 2. Set Up Environment

```bash
# Copier le modèle de configuration
cp .env.example .env

# Éditer .env : identifiants PostgreSQL, pgAdmin, modèle Ollama
```

> `.env` est ignoré par git. Ne le commitez jamais — les mots de passe y sont en clair.

### 3. Install Dependencies

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install packages
pip install -r requirements.txt
```

### 4. Install Ollama

```bash
# Install Ollama (macOS/Linux)
curl -fsSL https://ollama.com/install.sh | sh

# Start Ollama server
ollama serve

# Pull a model (in another terminal)
ollama pull llama3.2
```

### 5. Scrape Anthropic Docs

```bash
python scripts/scrape_anthropic.py
```

### 6. Ingest Documents

```bash
python scripts/ingest.py
```

### 7. Query the System

```bash
python scripts/query.py
```

## Project Structure

```
lighthouse-lab/
├── core/
│   ├── config.py           # ⭐ Tous les paramètres (modèles, chunking, DB, ...)
│   ├── db/                 # Connexion, schéma, requêtes SQL
│   ├── embeddings/         # Encodage des textes (bge-m3)
│   ├── ingestion/          # Chargement + chunking des documents
│   ├── retrieval/          # Recherche vectorielle + MMR
│   ├── generation/         # Client Ollama + prompts
│   ├── memory/             # Historique de conversation
│   └── rag/                # Orchestrateur du pipeline
├── data/
│   ├── raw/                # Documents scrapés (corpus actif)
│   └── backup/             # Anciens corpus (non ingérés)
├── scripts/
│   ├── scrape_anthropic.py # Web scraper (trafilatura)
│   ├── ingest.py           # Ingestion + déduplication
│   └── query.py            # CLI interactive
├── docker-compose.yml      # PostgreSQL + pgAdmin
├── requirements.txt        # Python dependencies
├── .env.example            # Environment template (copier en .env)
├── LICENSE
└── README.md
```

## Usage

### Interactive Query Mode

```bash
python scripts/query.py
```

Session interactive : pose une question, la réponse s'affiche avec ses sources.

| Commande | Effet |
|---|---|
| `quit` (ou `Ctrl+C`) | quitter |
| `clear` | effacer l'historique de la session |

### Programmatic Usage

```python
from core.rag.pipeline import RAGPipeline

# Initialize pipeline
pipeline = RAGPipeline()

# Ask a question
result = pipeline.ask("What is Claude's approach to AI safety?")

print(result["answer"])
print(result["sources"])
```

## Data pipeline (ingestion)

Ce qui se passe entre « je scrape le site » et « les chunks sont en base » :

```
① scrape_anthropic.py ──► ② loader ──► ③ chunking ──► ④ embed ──► ⑤ insert
   trafilatura              *.md        sections        bge-m3      Postgres
                          (486 docs)   (6 942)         (1024 d)    (1 transaction)
```

| Étape | Fichier | Ce qu'elle fait | Volumétrie actuelle |
|---|---|---|---|
| ① Scraping | `scripts/scrape_anthropic.py` | sitemap → filtre `/news /research /engineering /announcements` → `trafilatura` → Markdown | 492 pages → **486 docs** |
| ② Chargement | `core/ingestion/loader.py` | lit `data/raw/ai_engineering/*.md` | 486 documents |
| ③ Chunking | `core/ingestion/chunking.py` | découpe par titres Markdown, filtre `< 150` chars, dédup MD5 | **6 942 chunks** |
| ④ Embeddings | `core/embeddings/embedder.py` | bge-m3, par lots de 16, normalisés | 6 942 × 1024 dims |
| ⑤ Insertion | `core/db/connection.py` | `execute_values` + `commit()` unique | **6 942 lignes** |

**Propriétés importantes :**

- **Incrémental** — le scraper saute les fichiers déjà présents ; l'ingestion saute les `source`
  déjà en base. Relancer ne crée jamais de doublon.
- **Atomique** — tout est inséré à l'étape ⑤. Une interruption (Ctrl+C, fermeture VS Code, crash)
  laisse la base dans son état précédent : jamais de corpus à moitié écrit.
- **Rejouable** — `ingest.py` est idempotent, on peut le relancer sans risque.
- **Config du scraper dans le script** — `MAX_ARTICLES`, `REQUEST_DELAY` et `MIN_CONTENT_LENGTH`
  sont en haut de `scripts/scrape_anthropic.py` (ce sont des réglages de scraping, pas du RAG).

## Database management

```bash
# Vérifier l'état
docker exec lighthouse-db psql -U lighthouse -d lighthouse -c \
  "SELECT COUNT(*) AS chunks, COUNT(DISTINCT source) AS docs FROM documents;"

# Vider la table sans toucher au schéma (puis relancer ingest.py)
docker exec lighthouse-db psql -U lighthouse -d lighthouse -c \
  "TRUNCATE documents RESTART IDENTITY;"

# Réinitialiser complètement (schéma + données) — DESTRUCTIF
docker compose down -v && docker compose up -d
```

> `schema.sql` n'est exécuté **qu'à la création du volume**. Après un simple `down` / `up`,
> la table existe toujours. Pour la recréer il faut `down -v` (supprime le volume `pgdata`).

## Retrieval pipeline (current state)

Voici exactement ce qui se passe quand tu poses une question, et **où** chaque étape s'exécute.
Ce schéma est la référence : si un chiffre ou un composant change, cette section change aussi.

```
question
   │
   │ ① embedding de la question          → core/embeddings/embedder.py
   │    bge-m3 · 1024 dims · normalisé · local (MPS/CPU)
   ▼
┌─────────────────────────────────────────────────────────────┐
│ ② RECHERCHE COSINE — PostgreSQL + pgvector                  │
│    SQL : 1 - (embedding <=> query_vec) AS similarity        │
│    ORDER BY embedding <=> query_vec  LIMIT 40               │
│    → RETRIEVAL_CANDIDATES = 40 candidats                    │
│    (scan complet : aucun index HNSW/IVFFlat installé)       │
└─────────────────────────────────────────────────────────────┘
   │  40 chunks + leurs embeddings
   ▼
┌─────────────────────────────────────────────────────────────┐
│ ③ MMR — Python / numpy                                      │
│    score = 0.7 × similarité − 0.3 × redondance max          │
│    sélection itérative → TOP_K = 8 chunks diversifiés       │
└─────────────────────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────────────────────┐
│ ④ CONTEXTE — Python                                         │
│    concatène les chunks jusqu'à MAX_CONTEXT_LENGTH = 4000   │
└─────────────────────────────────────────────────────────────┘
   │
   ▼
⑤ GÉNÉRATION — Ollama (llama3.2, local)
```

**Points importants :**

- **Le cosine n'est pas remplacé par le MMR** — les deux travaillent en séquence.
  Postgres classe les 6 942 chunks par similarité cosine et renvoie les 40 meilleurs ;
  MMR choisit ensuite 8 parmi ces 40 en pénalisant ceux qui se ressemblent entre eux.
  Sans l'étape ②, MMR n'aurait aucun candidat ; sans l'étape ③, on renverrait 8 quasi-copies.
- **Pas d'index vectoriel à ce jour.** PostgreSQL fait un scan complet (quelques ms pour ~7 000
  chunks). Un index HNSW deviendra utile au-delà de ~100 000 chunks ; l'ajouter maintenant
  ajouterait un paramètre à régler (`ef_search`) pour un gain invisible.
- **Recherche exacte = meilleure qualité.** Un scan complet ne fait aucun compromis
  d'approximation, contrairement à un index ANN.
- **Le lexical n'existe pas encore.** Seul le dense est utilisé : c'est pour ça qu'un terme
  rare ou un acronyme peut être mal classé. C'est le rôle du hybrid search (étape 2 de la roadmap).

### État des lieux

| Composant | État |
|---|---|
| Scraping `trafilatura` (contenu principal, sans boilerplate) | ✅ fait |
| Chunking Markdown par section + filtre + dédup | ✅ fait |
| Embeddings bge-m3 (1024 dims) | ✅ fait |
| Base pgvector — 486 docs / 6 942 chunks, 0 doublon | ✅ à jour |
| Recherche cosine (Postgres) | ✅ fait |
| Diversité MMR | ✅ fait |
| **Hybrid search (dense + lexical, RRF)** | ❌ **pas encore** |
| **Reranker (`bge-reranker-v2-m3`)** | ❌ pas encore |
| Contextual retrieval | ❌ pas encore |
| Golden set / évaluation | ❌ pas encore |

## Architecture decisions

Cette section documente **pourquoi** chaque brique a été choisie. Elle sert de garde-fou :
avant d'ajouter une dépendance ou de changer une stratégie, on vérifie qu'on ne casse pas
un de ces choix.

### 1. Code RAG maison plutôt que LangChain complet

**Décision :** pipeline RAG écrit à la main (~800 lignes dans `core/`, ~1 200 au total avec les
scripts), LangChain utilisé uniquement via `langchain-text-splitters`.

**Pourquoi :**
- **Débogage** — à chaque étape (chunk, embedding, SQL, prompt) on peut lire et logger la donnée réelle.
  Un `Chain` opaque rend la traçabilité des erreurs de retrieval beaucoup plus difficile.
- **Schéma maison** — notre table `documents` (domain, source, chunk_index, content, embedding)
  est plus simple que les abstractions `Document`/`VectorStore` de LangChain.
- **Stabilité de l'API** — LangChain bouge vite ; le SQL et les appels `sentence-transformers` non.
- **Coût d'entrée** — on garde le splitter (le seul morceau réellement non-trivial) sans hériter
  du reste du framework.

**Quand reconsidérer :** si on ajoute des agents multi-étapes (LangGraph), ou si on a besoin de
connecteurs (PDF, Notion, web) — là l'écosystème fait gagner du temps.

### 2. pgvector plutôt qu'une base vectorielle dédiée

**Décision :** PostgreSQL + extension `pgvector`.

**Pourquoi :**
- **Un seul moteur** — vecteurs, métadonnées et (bientôt) full-text dans la même base : une
  seule transaction, un seul backup, un seul `docker-compose`.
- **Zéro dépendance supplémentaire** — pas de Qdrant/Weaviate/Chroma à faire tourner.
- **SQL complet** — filtres par domaine/date/source en `WHERE`, ce qu'on aurait de toute façon à
  réimplémenter ailleurs.
- **Suffisant à notre échelle** — ~7 000 chunks : un scan exact répond en quelques millisecondes.
  Aucun index vectoriel n'est installé pour l'instant (voir *Retrieval pipeline*).

**Limite assumée :** au-delà de quelques millions de vecteurs, une base dédiée serait plus rapide.
On y pensera si le corpus grossit d'un ordre de grandeur.

### 3. bge-m3 plutôt que MiniLM

**Décision :** `BAAI/bge-m3` (1024 dims) en remplacement de `all-MiniLM-L6-v2` (384 dims).

**Pourquoi :**
- **Multilingue** — questions en français, corpus en anglais : crucial pour nous.
- **Longue fenêtre** (8192 tokens) — même si nos chunks font ~1000 chars, on peut monter si besoin.
- **Pas d'instruction de requête** — contrairement à `bge-large-en`, pas de préfixe `"query: "` à gérer.
- **Trois modes natifs** (dense + sparse + ColBERT) — ouvre la porte au hybrid search et au
  reranking sans changer d'outil.
- **Qualité** — nettement au-dessus de MiniLM sur les benchmarks de retrieval.

**Coût :** 4,3 Go de poids, ~141 s au premier chargement, embeddings plus lents que MiniLM.
Acceptable, l'ingestion est ponctuelle et le retrieval reste interactif.

### 4. trafilatura plutôt que BeautifulSoup brut

**Décision :** extraction du contenu principal via `trafilatura.extract(..., output_format="markdown")`.

**Pourquoi — c'est un correctif, pas un luxe :** l'ancien scraper prenait tout le `<body>`.
Résultat mesuré sur le corpus précédent :

| Problème | Volume |
|---|---|
| Contenus présents dans >1 source (nav, « Related content », « Read more ») | 1 552 |
| Chunks < 100 chars (bruit) | 1 338 |
| Chunks au contenu exactement identique | 2 252 / 19 226 |

Conséquence concrète : sur une question, plusieurs des top-k résultats étaient **le même
boilerplate**, donc le LLM recevait du bruit répété au lieu de contenu.

`trafilatura` supprime nav/header/footer/aside et les blocs de recommandation, et sort du
Markdown avec de vrais titres — ce qui alimente directement le chunking par section.

### 5. Chunking Markdown-aware plutôt que découpe fixe

**Décision :** `MarkdownHeaderTextSplitter` (H1/H2/H3) + fallback `RecursiveCharacterTextSplitter`
pour les sections trop longues, puis filtrage et déduplication.

**Pourquoi :**
- **Cohérence sémantique** — un chunk = une idée / une sous-section. Couper tous les 500 chars
  sépare une question de sa réponse, ou mélange deux sujets.
- **Titres conservés dans le texte** (`strip_headers=False`) — le titre aide l'embedding à situer
  le passage, et le LLM à comprendre d'où vient l'extrait.
- **Filtre `MIN_CHUNK_LENGTH`** — élimine les titres orphelins et séparateurs qui polluaient le top-k.
- **Dédup à deux niveaux** — par document (dans `chunking.py`) puis globale par MD5 (dans `ingest.py`),
  pour qu'un même contenu n'occupe jamais deux places dans le contexte.

### 6. Récupération large puis MMR plutôt que top-k direct

**Décision :** récupérer `RETRIEVAL_CANDIDATES = 40` chunks, puis sélectionner `TOP_K = 8` par
**MMR** (Maximal Marginal Relevance).

**Pourquoi :**
- **Le top-k dense ne rate pas l'info, il la mal classe.** Le bon passage peut être 15ᵉ ; un
  top-5 direct le jette.
- **MMR pénalise la redondance** — sans lui, 5 résultats peuvent être 5 variantes du même paragraphe.
  `MMR_LAMBDA = 0.7` = 70 % pertinence, 30 % diversité.
- **Élargir avant de filtrer** est le principe commun à tous les RAG avancés : c'est ce pool de
  candidats qu'un reranker exploitera à l'étape suivante.

### 7. Contexte borné

**Décision :** `MAX_CONTEXT_LENGTH = 4000` caractères, chunks ajoutés dans l'ordre jusqu'à la limite.

**Pourquoi :** un contexte trop long dilue l'attention du LLM et allonge la génération. On préfère
8 chunks pertinents à 30 chunks moyens.

### 8. Golden set et évaluation (à venir)

**Décision :** construire un jeu de questions/réponses de référence et mesurer **Recall@k** et **MRR**.

**Pourquoi :** sans mesure, chaque changement (hybrid, reranker, contextual retrieval) est une
impression subjective. On ne peut pas améliorer ce qu'on ne mesure pas.

## Roadmap

- [x] **0. Nettoyage des données** — trafilatura, chunking Markdown, dédup, filtre de bruit
- [x] **1. Diversité** — MMR sur un pool élargi de candidats
- [ ] **2. Hybrid search** — dense (pgvector) + lexical (Postgres `tsvector`/`ts_rank`), fusion **RRF**
- [ ] **3. Reranker** — `bge-reranker-v2-m3` sur 30–50 candidats → top 5
- [ ] **4. Contextual Retrieval** — préfixer chaque chunk d'un résumé du document avant embedding
- [ ] **5. Évaluation** — golden set, Recall@k, MRR
- [ ] **6. Mémoire persistante** (Redis), interface web, API

> **Ordre choisi :** données propres → diversité → hybrid → rerank → contexte → mesure.
> Un reranker ne sauve pas un corpus pollué : nettoyer d'abord est le gain le plus rentable.

## Development

### Adding New Documents

1. Place markdown files in `data/raw/ai_engineering/`
2. Run ingestion: `python scripts/ingest.py`

L'ingestion est **idempotente** : les sources déjà présentes sont ignorées, et tous les inserts
se font dans une seule transaction (interrompre le script ne laisse jamais de données partielles).

### Tuning the Pipeline

**Tous les paramètres du système se trouvent dans un seul fichier : `core/config.py`**

| Paramètre | Rôle | Défaut |
|---|---|---|
| `EMBEDDING_MODEL_NAME` | Modèle d'embedding | `BAAI/bge-m3` |
| `EMBEDDING_DIMENSION` | Taille du vecteur (doit matcher le modèle **et** `schema.sql`) | `1024` |
| `EMBEDDING_BATCH_SIZE` | Taille de lot d'encodage | `16` |
| `EMBEDDING_NORMALIZE` | Normalise les vecteurs (requis pour cosine) | `True` |
| `EMBEDDING_MAX_SEQ_LENGTH` | Tokens max pris en compte par le modèle | `512` |
| `CHUNK_SIZE` | Taille max d'un chunk (caractères) | `1000` |
| `CHUNK_OVERLAP` | Chevauchement entre chunks | `150` |
| `MIN_CHUNK_LENGTH` | En dessous → chunk ignoré | `150` |
| `TOP_K` | Chunks finaux envoyés au LLM | `8` |
| `RETRIEVAL_CANDIDATES` | Candidats récupérés avant MMR / rerank | `40` |
| `MMR_LAMBDA` | 0 = diversité max, 1 = pertinence pure | `0.7` |
| `MAX_CONTEXT_LENGTH` | Longueur max du contexte (caractères) | `4000` |
| `LLM_MODEL` | Modèle Ollama | `llama3.2` |
| `LLM_TEMPERATURE` / `LLM_MAX_TOKENS` | Génération | `0.7` / `1024` |
| `DEFAULT_DOMAIN` | Domaine par défaut | `ai_engineering` |

> **Changer de modèle d'embedding :** modifier `EMBEDDING_MODEL_NAME` **et** `EMBEDDING_DIMENSION`
> (ainsi que la colonne dans `core/db/schema.sql`), vider la table, puis relancer
> `python scripts/ingest.py`. Les embeddings de deux modèles ne sont pas comparables.

Les prompts se modifient dans `core/generation/prompts.py`.

## Troubleshooting

| Symptôme | Cause probable | Solution |
|---|---|---|
| `could not connect to server` | Postgres arrêté | `docker compose up -d` puis `docker ps` |
| `relation "documents" does not exist` | Volume créé avant `schema.sql` | `docker compose down -v && docker compose up -d` |
| `Connection refused` sur Ollama | `ollama serve` non lancé | `ollama serve` (ou ouvrir l'app Ollama) |
| Ingestion très lente au 1er batch | téléchargement + compilation MPS | attendre, c'est normal (~2–3 min) |
| `MPS backend out of memory` | lots trop gros | baisser `EMBEDDING_BATCH_SIZE` dans `core/config.py` |
| Modèle qui se re-télécharge | cache HF vidé / autre `HF_HOME` | vérifier `~/.cache/huggingface/hub/models--BAAI--bge-m3` |
| `Ctrl+C` pendant l'ingestion | — | **sans risque** : transaction unique, rien n'est écrit |
| Résultats hors sujet | bruit lexical / terme rare | c'est l'objet du hybrid search + reranker (roadmap) |

> **Astuce macOS :** l'ingestion dure ~7 min et la veille peut interrompre le process.
> Préfixez par `caffeinate -i python scripts/ingest.py`.

## License

MIT — voir [`LICENSE`](LICENSE).
