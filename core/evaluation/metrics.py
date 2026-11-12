"""
Métriques d'évaluation du retrieval.

Fonctions pures : elles ne connaissent ni la base, ni les embeddings, ni les
modèles. En entrée, un classement de noms de fichiers ; en sortie, des nombres.

Trois métriques, trois questions différentes :

    Recall@k   « la bonne info est-elle quelque part dans le top k ? »
               → 1 si au moins un document attendu est présent, sinon 0.
               C'est la métrique qui compte : un LLM ne peut pas répondre
               avec un contexte qui ne contient pas l'information.

    MRR        « à quel rang arrive le premier bon document ? »
               → moyenne de 1/rang. 1.0 = toujours en tête, 0.5 = rang 2.
               Mesure la qualité du classement, pas seulement la présence.

    Couverture « quelle proportion des documents attendus est retrouvée ? »
               → utile quand plusieurs documents sont pertinents (sujets
               transverses). Recall@k vaut 1 dès le premier trouvé, la
               couverture non.
"""


def first_hit_rank(retrieved: list[str], expected: set[str]) -> int | None:
    """Rang (1-based) du premier document attendu, ou None s'il est absent."""
    for rank, source in enumerate(retrieved, start=1):
        if source in expected:
            return rank
    return None


def evaluate(
    questions: list[dict],
    results: dict[str, list[str]],
    k: int,
) -> dict:
    """
    Calcule les métriques sur l'ensemble du golden set.

    Args:
        questions: liste de dicts avec `id`, `question`, `expected_sources`
        results:   {id: [source, source, ...]} — ordre = classement du retrieval
        k:         profondeur d'évaluation (on ne regarde que les k premiers)

    Returns:
        {
          "k": 5,
          "n": 20,
          "recall_at_k": 0.85,
          "mrr": 0.72,
          "coverage": 0.66,
          "rows": [{"id", "question", "rank", "found", "expected_n"}, ...],
        }
    """
    rows = []
    hits = 0
    reciprocal_ranks = 0.0
    coverage_sum = 0.0

    for question in questions:
        expected = set(question["expected_sources"])
        retrieved = results.get(question["id"], [])[:k]

        rank = first_hit_rank(retrieved, expected)
        found = len(expected & set(retrieved))

        hits += 1 if rank else 0
        reciprocal_ranks += (1.0 / rank) if rank else 0.0
        coverage_sum += (found / len(expected)) if expected else 0.0

        rows.append(
            {
                "id": question["id"],
                "question": question["question"],
                "rank": rank,
                "found": found,
                "expected_n": len(expected),
            }
        )

    n = len(questions) or 1

    return {
        "k": k,
        "n": len(questions),
        "recall_at_k": hits / n,
        "mrr": reciprocal_ranks / n,
        "coverage": coverage_sum / n,
        "rows": rows,
    }
