#!/usr/bin/env python3
"""
Compare la recherche avec et sans reranker, sur un jeu de requêtes fixe.

Usage :
    python scripts/eval_retrieval.py

Affiche, pour chaque requête, les résultats des deux modes et leur latence.
C'est aussi la base du futur golden set (étape 5 de la roadmap).
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from core.retrieval.hybrid_search import hybrid_search

console = Console()

TOP_K = 5

QUERIES = [
    # Expression de 3 mots courants : le lexical produit du bruit
    "Model Hardware Standard",
    # Terme technique rare
    "interpretability",
    # Question naturelle
    "How does Claude watermark generated text?",
    # Sujet transverse
    "What is constitutional AI?",
]


def run(query: str, use_rerank: bool) -> tuple[list[dict], float]:
    start = time.perf_counter()
    results = hybrid_search(query, top_k=TOP_K, use_rerank=use_rerank)
    return results, time.perf_counter() - start


def main():
    console.print("[bold blue]🔬 Évaluation du retrieval[/bold blue]")
    console.print(f"   {len(QUERIES)} requêtes · top_k={TOP_K}\n")

    for query in QUERIES:
        console.print(f"[bold]❓ {query}[/bold]")

        without, time_without = run(query, use_rerank=False)
        with_, time_with = run(query, use_rerank=True)

        ids_without = {(r["source"], r["chunk_index"]) for r in without}
        ids_with = {(r["source"], r["chunk_index"]) for r in with_}

        console.print(f"   [dim]sans reranker[/dim] ({time_without:.2f}s)")
        for i, r in enumerate(without, 1):
            console.print(f"     {i}. {r['source']} [{r['chunk_index']}]")

        console.print(f"   [green]avec reranker[/green] ({time_with:.2f}s)  "
                      f"[dim]★ = nouveau[/dim]")
        for i, r in enumerate(with_, 1):
            mark = "  " if (r["source"], r["chunk_index"]) in ids_without else "★ "
            console.print(f"     {mark}{i}. {r['source']} [{r['chunk_index']}]")

        common = len(ids_without & ids_with)
        console.print(f"   [dim]communs : {common}/{TOP_K} · "
                      f"latence ×{time_with / time_without:.1f}[/dim]\n")


if __name__ == "__main__":
    main()
