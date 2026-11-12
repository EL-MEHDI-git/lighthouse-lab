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
| Recherche | pgvector (dense) + Postgres FTS (lexical), fusion RRF | Comprend le sens **et** les termes exacts, sans dépendance supplémentaire |
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
│   ├── evaluation/         # Métriques (Recall@k, MRR) — fonctions pures
│   ├── ingestion/          # Chargement + chunking des documents
│   ├── retrieval/          # dense + lexical, RRF, reranker, MMR
│   ├── generation/         # Client Ollama + prompts
│   ├── memory/             # Historique de conversation
│   └── rag/                # Orchestrateur du pipeline
├── eval/
│   ├── golden/             # Questions de référence (YAML, un fichier par domaine)
│   └── results/            # Historique des mesures (JSON, versionné)
├── data/
│   ├── raw/                # Documents scrapés (corpus actif)
│   └── backup/             # Anciens corpus (non ingérés)
├── scripts/
│   ├── scrape_anthropic.py # Web scraper (trafilatura)
│   ├── ingest.py           # Ingestion + déduplication
│   ├── query.py            # CLI interactive
│   ├── eval_golden.py      # Golden set → Recall@k / MRR
│   └── eval_retrieval.py   # A/B visuel avec et sans reranker
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

### Évaluer le retrieval

Deux outils, deux questions différentes :

| Script | Question | Sortie |
|---|---|---|
| `scripts/eval_golden.py` | **est-ce que ça s'améliore ?** | Recall@k, MRR, JSON versionné |
| `scripts/eval_retrieval.py` | **pourquoi ?** | comparaison visuelle côte à côte |

#### Golden set

20 questions de référence, dans `eval/golden/ai_engineering.yaml`. Chaque question
liste les documents qui **devraient** apparaître dans le top-k.

```bash
python scripts/eval_golden.py                      # pipeline complet (défaut)
python scripts/eval_golden.py --config hybrid      # sans reranker
python scripts/eval_golden.py --config dense       # cosine seule
python scripts/eval_golden.py --top-k 8
```

Le script valide le golden set avant de mesurer : chaque `expected_source` doit exister
en base et chaque `anchor` doit être présent dans le document. Un golden set cassé fait
échouer la commande — une mesure sur des données invalides ne vaut rien.

| Métrique | Question | Calcul |
|---|---|---|
| **Recall@k** | la bonne info est-elle dans le top k ? | 1 si au moins un document attendu est présent |
| **MRR** | à quel rang arrive le premier bon document ? | moyenne de `1/rang` |
| **Couverture** | quelle part des documents attendus est retrouvée ? | utile pour les sujets transverses |

Résultat par défaut sauvegardé dans `eval/results/<date>_<config>.json` — l'historique
est versionné, donc on peut comparer deux mois plus tard.

**Pourquoi des `source` et pas des IDs de chunks ?** Les IDs changent à chaque
re-découpage. Les noms de fichiers non. Le golden set survit ainsi au re-chunking,
au re-embedding et au contextual retrieval.

#### Mesure de référence (20 questions, 11/11/2026)

| Configuration | Recall@5 | MRR | Couverture | Temps/question |
|---|---|---|---|---|
| `dense` | 0.95 | **0.86** | 0.85 | 0.36 s |
| `hybrid` | **1.00** | 0.84 | **0.92** | 0.36 s |
| `hybrid+rerank` | 0.95 | 0.82 | 0.90 | 2.05 s |

**Ce que ça dit :**

- **Le hybrid gagne** : il retrouve un document attendu pour **20 questions sur 20**
  (contre 19 en dense), grâce au lexical sur `ASL-3`. Coût identique.
- **Le reranker ne gagne pas** : −5 % de rappel, −0.02 de MRR, pour **5,7× plus de temps**.
  Vérifié sans MMR : mêmes chiffres (0.95 / 0.82). Ce n'est donc pas MMR qui l'annule,
  c'est le cross-encoder lui-même qui reclasse mal sur ce corpus.
  → `RERANK_ENABLED = False` par défaut. Le code reste, le flag permet de le réactiver.

> ⚠️ 20 questions, c'est petit : un écart de 0.05 = **une seule question**. Ces chiffres
> servent à détecter des régressions franches, pas à départager deux variantes proches.
> Enrichir le golden set avant de trancher sur des écarts < 0.05.

#### Ajouter une question

```yaml
- id: q21                     # prochain id libre, ne jamais réutiliser
  question: "…"
  category: natural           # acronym | lexical_noise | natural | concept | product
  expected_sources:
    - news_le-document.md     # au moins un doit être dans le top-k
  anchor: "extrait de texte présent dans le document"
  notes: "pourquoi ce cas est intéressant"
```

#### Comparaison visuelle (A/B)

```bash
python scripts/eval_retrieval.py
```

Affiche, pour 4 requêtes, les résultats **avec** et **sans** reranker côte à côte,
avec la latence et le nombre de résultats communs. Utile pour comprendre *pourquoi*
un chiffre a bougé, pas pour le mesurer.

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

### Migrer une base existante (hybrid search)

Une base créée **avant** le hybrid search n'a pas la colonne `content_tsv`. Sans elle, le
full-text échoue. Migration idempotente :

```sql
ALTER TABLE documents
  ADD COLUMN IF NOT EXISTS content_tsv tsvector
  GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;

CREATE INDEX IF NOT EXISTS documents_content_tsv_idx ON documents USING GIN (content_tsv);
CREATE INDEX IF NOT EXISTS documents_domain_idx      ON documents (domain);
```

```bash
docker exec -i lighthouse-db psql -U lighthouse -d lighthouse < migration.sql
```

## Retrieval pipeline (current state)

Voici exactement ce qui se passe quand tu poses une question, et **où** chaque étape s'exécute.
Ce schéma est la référence : si un chiffre ou un composant change, cette section change aussi.

```
question
   │
   │ ① embedding de la question          → core/embeddings/embedder.py
   │    bge-m3 · 1024 dims · normalisé · local (MPS/CPU)
   │
   ├──────────────────────────────┬──────────────────────────────────┐
   ▼                              ▼                                  │
┌──────────────────────┐   ┌──────────────────────────────────┐     │
│ ②a DENSE             │   │ ②b LEXICAL                       │     │
│ pgvector · cosine    │   │ Postgres full-text               │     │
│ ORDER BY embedding   │   │ websearch_to_tsquery('english')  │     │
│ LIMIT 40             │   │ ts_rank_cd → LIMIT 40            │     │
└──────────────────────┘   └──────────────────────────────────┘     │
   │ 40 candidats              │ 40 candidats                        │
   └────────────┬──────────────┘                                    │
                ▼                                                   │
┌──────────────────────────────────────────────────────┐            │
│ ③ FUSION RRF — Python                                │            │
│ score = 1/(60+rang_dense) + 0.5/(60+rang_lexical)    │            │
│ → 40 meilleurs candidats fusionnés                   │            │
└──────────────────────────────────────────────────────┘            │
                │                                                   │
                ▼                                                   │
┌──────────────────────────────────────────────────────┐            │
│ ④ RERANKER — cross-encoder (bge-reranker-v2-m3)      │            │
│ OPTIONNEL · RERANK_ENABLED = False par défaut        │            │
│ lit (question, chunk) ensemble → pertinence réelle   │            │
│ → 40 candidats re-triés                              │            │
└──────────────────────────────────────────────────────┘            │
                │                                                   │
                ▼                                                   │
┌──────────────────────────────────────────────────────┐            │
│ ⑤ MMR — Python / numpy                               │            │
│ pertinence = reranker ou RRF · redondance = cosine   │            │
│ score = 0.7 × pertinence − 0.3 × redondance          │            │
│ → TOP_K = 8 chunks diversifiés                       │            │
└──────────────────────────────────────────────────────┘            │
                │                                                   │
                ▼                                                   │
┌──────────────────────────────────────────────────────┐            │
│ ⑥ CONTEXTE — concatène jusqu'à 4 000 caractères      │            │
└──────────────────────────────────────────────────────┘            │
                │                                                   │
                ▼                                                   │
⑦ GÉNÉRATION — Ollama (llama3.2, local) ◄───────────────────────────┘
```

**Points importants :**

- **Deux recherches en parallèle, une seule fusion.** Le dense comprend le *sens*, le lexical
  trouve les *mots exacts* (acronymes, noms propres, chiffres). Aucun des deux ne gagne seul.
- **RRF ne compare que des rangs, jamais des scores.** Cosine ∈ [-1, 1] et `ts_rank_cd` ∈ [0, ~1]
  n'ont ni la même échelle ni la même distribution : les additionner exigerait une normalisation
  fragile. `1/(60+rang)` est insensible à l'échelle → zéro réglage.
- **`LEXICAL_WEIGHT = 0.5`** — le lexical pèse moitié moins que le dense. `ts_rank_cd` n'est pas
  BM25 : il récompense les mots fréquents du corpus (« model », « standard »), ce qui fait remonter
  du bruit. À 1.0, un chunk hors sujet apparaissait ; à 0.5, il disparaît.
- **MMR utilise le score du reranker (ou du RRF) comme pertinence**, pas le cosine. Sinon un
  chunk trouvé *uniquement* par le lexical (cosine moyen) serait éliminé, ce qui annulerait tout
  l'intérêt du hybrid. Le cosine sert seulement à mesurer la redondance **entre** candidats.
- **Le reranker ne remplace ni RRF ni MMR** — chacun a un rôle distinct :

  | Couche | Rôle | Question |
  |---|---|---|
  | RRF | **rappel** | quels candidats entrent dans le pool ? |
  | Reranker | **précision** | lesquels répondent vraiment ? |
  | MMR | **diversité** | lesquels garder sans répéter ? |
- **Le reranker est désactivé par défaut**, sur la foi du golden set : Recall@5 0.95 contre 1.00
  sans lui, MRR 0.82 contre 0.84, pour 5,7× plus de temps. Le module et le flag restent en place.
- **Pas d'index vectoriel à ce jour.** PostgreSQL fait un scan complet (quelques ms pour ~7 000
  chunks). Un index HNSW deviendra utile au-delà de ~100 000 chunks.
- **Index GIN sur `content_tsv`** — sans lui, le full-text ferait aussi un scan complet.
- **Recherche exacte = meilleure qualité** côté dense : aucun compromis d'approximation.
- **Limite connue :** le lexical est configuré en `'english'`. Une question en français ne matchera
  pas lexicalement — mais le dense porte seul, la fusion restant correcte.

### État des lieux

| Composant | État |
|---|---|
| Scraping `trafilatura` (contenu principal, sans boilerplate) | ✅ fait |
| Chunking Markdown par section + filtre + dédup | ✅ fait |
| Embeddings bge-m3 (1024 dims) | ✅ fait |
| Base pgvector — 486 docs / 6 942 chunks, 0 doublon | ✅ à jour |
| Recherche cosine (Postgres) | ✅ fait |
| Diversité MMR | ✅ fait |
| **Hybrid search** (dense + lexical, RRF) | ✅ fait |
| **Reranker (`bge-reranker-v2-m3`)** | ✅ code fait · ⚪ désactivé (mesuré sans gain) |
| Contextual retrieval | ❌ pas encore |
| **Golden set / évaluation** | ✅ 20 questions, Recall@5 / MRR |

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
  candidats qu'exploite le reranker (décision 9).

### 7. Contexte borné

**Décision :** `MAX_CONTEXT_LENGTH = 4000` caractères, chunks ajoutés dans l'ordre jusqu'à la limite.

**Pourquoi :** un contexte trop long dilue l'attention du LLM et allonge la génération. On préfère
8 chunks pertinents à 30 chunks moyens.

### 8. Hybrid search plutôt que dense seul

**Décision :** interroger en parallèle le dense (pgvector) et le lexical (Postgres full-text),
puis fusionner les deux classements par **RRF pondéré**.

**Pourquoi :**
- **Les deux méthodes échouent sur des cas complémentaires.** Le dense rate les termes rares
  (acronyme, nom de produit, chiffre) ; le lexical rate les reformulations. Mesuré sur notre
  corpus : pour la requête `interpretability`, **26 des 40 candidats lexicaux sont absents du
  top-40 dense**.
- **Postgres FTS plutôt que BM25 de LangChain** — même moteur que les vecteurs, index GIN,
  filtres `domain` en SQL, rien à resynchroniser. `rank_bm25` exige un index **en RAM reconstruit
  à chaque démarrage**.
- **RRF plutôt qu'une somme pondérée de scores** — insensible à l'échelle des scores, donc pas de
  normalisation fragile. Un seul paramètre à régler.
- **`LEXICAL_WEIGHT = 0.5`** — `ts_rank_cd` n'est pas BM25 : il survalorise les mots fréquents du
  corpus (« model », « standard »). Constaté : à `1.0`, un chunk hors sujet entrait dans le top-8 ;
  à `0.5`, il sort.

**Limites assumées :**
- `ts_rank_cd` n'a pas la saturation de fréquence de BM25. Le reranker (décision 9) corrige
  ce bruit résiduel.
- Configuration `'english'` : une question française ne matche pas lexicalement. Le dense porte
  alors seul, la fusion restant cohérente.
- Le mode **sparse natif de bge-m3** serait plus fidèle, mais impose de stocker des vecteurs creux
  et un moteur capable de les interroger. Reporté.

### 9. Reranker cross-encoder plutôt que similarité de vecteurs seule

**Décision :** après la fusion RRF, re-trier les 40 candidats avec `BAAI/bge-reranker-v2-m3`,
puis sélectionner les 8 finaux par MMR.

**Pourquoi :**
- **Un bi-encoder (bge-m3) encode la question et le chunk séparément** : il compare deux points
  dans l'espace vectoriel sans jamais lire les deux ensemble. Un **cross-encoder** lit
  `(question, chunk)` dans la même passe : il juge la pertinence réelle.
- C'est ce qui élimine le bruit lexical résiduel — par exemple un chunk qui matche les mots
  « model », « hardware », « standard » sans parler du *Model Hardware Standard*.
- **Coût O(n)** (un forward par candidat) : d'où son usage en dernière étape sur 40 candidats,
  jamais sur les 7 000 chunks du corpus.

**Pourquoi MMR reste après le reranker :** le cross-encoder va naturellement remonter plusieurs
chunks du **même** document (ils sont tous pertinents). Sans MMR, le contexte redevient redondant.
Le reranker remplace le *signal de pertinence*, pas la *diversification*.

**Sûreté :** `RERANK_ENABLED = False` restaure exactement le comportement précédent. Si le modèle
ne charge pas (mémoire, réseau), un warning est émis et les scores RRF sont conservés — la
recherche continue de fonctionner.

**Détail qui compte :** les scores du reranker sont normalisés en **min-max** avant MMR, pas
divisés par le max. Sinon tous les scores restent tassés près de 1 et la pénalité de redondance
(0,3) domine : un chunk hors sujet mais divers bat un chunk pertinent mais redondant. Constaté
sur `Model Hardware Standard` — deux chunks hors sujet entraient dans le top 5.

**Coût mesuré :** 2,3 Go de poids, **+1,1 à 1,2 s par requête** sur MPS (le premier appel paie en
plus le chargement du modèle, ~7 s). Le ratio « ×15 » affiché par le script est trompeur : il
compare à une recherche sans reranker qui prend 0,1 s.

**Verdict du golden set (11/11/2026) — le reranker n'est pas rentable ici :**

| Configuration | Recall@5 | MRR | Temps/question |
|---|---|---|---|
| `hybrid` (sans reranker) | **1.00** | **0.84** | 0.36 s |
| `hybrid+rerank` | 0.95 | 0.82 | 2.05 s |

Il fait perdre un document attendu, dégrade légèrement le MRR, et coûte **5,7× plus cher**.
Vérification faite **sans MMR** (prendre directement son top-5) : mêmes chiffres — ce n'est donc
pas MMR qui l'annule, c'est le cross-encoder lui-même qui reclasse mal sur ce corpus.
→ `RERANK_ENABLED = False` par défaut. Le module reste en place : c'est un flag à réactiver
quand le golden set sera plus large, ou avec un autre modèle.

### 10. Golden set et évaluation

**Décision :** mesurer chaque amélioration au lieu de la juger à l'œil.

**Ce qui existe :** `eval/golden/ai_engineering.yaml` — 20 questions couvrant 5 catégories
(acronyme, bruit lexical, question naturelle, concept transverse, produit). Chaque question
liste ses documents attendus. `scripts/eval_golden.py` calcule **Recall@5**, **MRR** et la
**couverture**, et sauvegarde un JSON dans `eval/results/`.

**Pourquoi des `source` et pas des IDs de chunks :** les IDs changent à chaque re-découpage.
Le golden set doit survivre au chunking, au re-embedding et au contextual retrieval — sinon
il faut le refaire à chaque expérience.

**Validation intégrée :** le script vérifie que chaque source existe en base et que chaque
ancre est présente dans le document. Un golden set périmé échoue bruyamment au lieu de
produire des chiffres faux.

**Limite assumée :** 20 questions, c'est petit. Un écart de 0.05 = une question. Le golden set
détecte les régressions franches, pas les gains marginaux. Il s'enrichit au fil des domaines.

**Ce que ça a déjà changé :** le reranker a été désactivé sur la base de ces chiffres
(décision 9) — alors qu'il « semblait » meilleur à l'œil sur les tests manuels.

**Pourquoi :** sans mesure, chaque changement (hybrid, reranker, contextual retrieval) est une
impression subjective. On ne peut pas améliorer ce qu'on ne mesure pas.

## Roadmap

- [x] **0. Nettoyage des données** — trafilatura, chunking Markdown, dédup, filtre de bruit
- [x] **1. Diversité** — MMR sur un pool élargi de candidats
- [x] **2. Hybrid search** — dense (pgvector) + lexical (Postgres `tsvector`/`ts_rank_cd`), fusion **RRF**
- [x] **3. Reranker** — `bge-reranker-v2-m3` implémenté, **désactivé** (mesuré sans gain)
- [ ] **4. Contextual Retrieval** — préfixer chaque chunk d'un résumé du document avant embedding
- [x] **5. Évaluation** — golden set 20 questions, Recall@5 / MRR / couverture
- [ ] **6. Variantes de chunking** — tables séparées, comparées sur le golden set
- [ ] **7. Mémoire persistante** (Redis), interface web, API

> **Ordre choisi :** données propres → diversité → hybrid → rerank → **mesure** → contexte.
> Un reranker ne sauve pas un corpus pollué : nettoyer d'abord est le gain le plus rentable.
> Et sans golden set, on ne sait pas si une couche aide — le reranker en est la preuve.

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
| `RETRIEVAL_CANDIDATES` | Candidats denses récupérés avant fusion | `40` |
| `MMR_LAMBDA` | 0 = diversité max, 1 = pertinence pure | `0.7` |
| `HYBRID_ENABLED` | Active dense + lexical (sinon dense seul) | `True` |
| `LEXICAL_CANDIDATES` | Candidats full-text récupérés | `40` |
| `RRF_K` | Constante de fusion RRF | `60` |
| `LEXICAL_WEIGHT` | Poids du lexical dans la fusion | `0.5` |
| `RERANK_ENABLED` | Active le cross-encoder (sinon scores RRF) | `False` |
| `RERANK_MODEL` | Modèle de reranking | `BAAI/bge-reranker-v2-m3` |
| `RERANK_CANDIDATES` | Candidats envoyés au cross-encoder | `40` |
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
| Résultats hors sujet | bruit lexical résiduel / terme rare | ajuster `LEXICAL_WEIGHT` ou `RERANK_CANDIDATES` |

> **Astuce macOS :** l'ingestion dure ~7 min et la veille peut interrompre le process.
> Préfixez par `caffeinate -i python scripts/ingest.py`.

## License

MIT — voir [`LICENSE`](LICENSE).
