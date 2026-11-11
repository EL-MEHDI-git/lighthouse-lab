#!/usr/bin/env python3
"""
Évalue le retrieval contre le golden set.

Le script ne modifie rien : il lit les questions, lance la recherche, calcule
les métriques et (par défaut) sauvegarde le résultat dans eval/results/.

Usage :
    python scripts/eval_golden.py                        # hybrid+rerank, top 5
    python scripts/eval_golden.py --config dense         # cosine seule
    python scripts/eval_golden.py --config hybrid        # sans reranker
    python scripts/eval_golden.py --top-k 8
    python scripts/eval_golden.py --no-save              # ne rien écrire

Configurations :
    dense           vector_search (cosine, Postgres)
    hybrid          dense + lexical + RRF, sans reranker
    hybrid+rerank   pipeline complet (défaut)

Métriques :
    Recall@k   au moins un document attendu dans le top k
    MRR        1 / rang du premier document attendu
    Couverture proportion des documents attendus retrouvés (sujets transverses)

Les questions sont validées avant l'exécution : chaque `expected_source` doit
exister en base et chaque `anchor` doit être présent dans le document. Une
question cassée fait échouer le script — c'est volontaire, une mesure sur un
golden set invalide ne vaut rien.
"""
import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
from rich.console import Console
from rich.table import Table

from core.config import DEFAULT_DOMAIN
from core.db.connection import get_connection
from core.evaluation.metrics import evaluate
from core.retrieval.hybrid_search import hybrid_search
from core.retrieval.vector_search import vector_search

console = Console()

CONFIGS = ("dense", "hybrid", "hybrid+rerank")
RESULTS_DIR = Path(__file__).parent.parent / "eval" / "results"


def load_golden(path: Path) -> list[dict]:
    """Charge et valide la structure minimale du fichier YAML."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    questions = data.get("questions", [])

    if not questions:
        raise SystemExit(f"❌ Aucune question dans {path}")

    for question in questions:
        missing = {"id", "question", "expected_sources"} - question.keys()
        if missing:
            raise SystemExit(
                f"❌ {path.name} : {question.get('id', '?')} — champs manquants {missing}"
            )

    return questions


def validate(questions: list[dict], conn) -> list[str]:
    """
    Vérifie que le golden set est encore valide par rapport à la base.

    Deux contrôles :
      1. chaque source attendue existe
      2. l'ancre est bien présente dans la première source attendue
    """
    problems = []
    with conn.cursor() as cur:
        for question in questions:
            for source in question["expected_sources"]:
                cur.execute("SELECT COUNT(*) FROM documents WHERE source = %s", (source,))
                if cur.fetchone()[0] == 0:
                    problems.append(f"{question['id']} : source absente → {source}")

            anchor = question.get("anchor")
            if anchor:
                source = question["expected_sources"][0]
                cur.execute(
                    "SELECT COUNT(*) FROM documents WHERE source = %s AND content ILIKE %s",
                    (source, f"%{anchor}%"),
                )
                if cur.fetchone()[0] == 0:
                    problems.append(
                        f"{question['id']} : ancre introuvable dans {source} → {anchor!r}"
                    )
    return problems


def retrieve(question: str, config: str, top_k: int, domain: str) -> list[dict]:
    """Lance la recherche selon la configuration demandée."""
    if config == "dense":
        return vector_search(question, top_k, domain)
    if config == "hybrid":
        return hybrid_search(question, top_k, domain, use_rerank=False)
    return hybrid_search(question, top_k, domain, use_rerank=True)


def print_report(config: str, metrics: dict, elapsed: float, domain: str) -> None:
    """Affiche le détail par question puis le résumé."""
    table = Table(title=f"{config} · top-{metrics['k']} · domaine {domain}")
    table.add_column("id", style="dim")
    table.add_column("rang", justify="right")
    table.add_column("question", overflow="fold")
    table.add_column("trouvés", justify="right", style="dim")

    for row in metrics["rows"]:
        if row["rank"]:
            rank = f"[green]{row['rank']}[/green]"
        else:
            rank = "[red]—[/red]"
        table.add_row(
            row["id"],
            rank,
            row["question"],
            f"{row['found']}/{row['expected_n']}",
        )

    console.print(table)
    console.print(
        f"\n[bold]Recall@{metrics['k']}[/bold] : {metrics['recall_at_k']:.2f}   "
        f"[bold]MRR[/bold] : {metrics['mrr']:.2f}   "
        f"[bold]Couverture[/bold] : {metrics['coverage']:.2f}"
    )
    console.print(
        f"[dim]{metrics['n']} questions · {elapsed / metrics['n']:.2f} s/question[/dim]"
    )


def save_result(config: str, metrics: dict, elapsed: float, domain: str) -> Path:
    """Sauvegarde le résultat pour garder un historique comparable."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    output = RESULTS_DIR / f"{timestamp}_{config.replace('+', '-')}.json"

    payload = {
        "timestamp": timestamp,
        "domain": domain,
        "config": config,
        "elapsed_seconds": round(elapsed, 2),
        **metrics,
    }
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Évalue le retrieval contre le golden set.")
    parser.add_argument(
        "--golden",
        type=Path,
        default=Path(__file__).parent.parent / "eval" / "golden" / "ai_engineering.yaml",
        help="fichier YAML du golden set",
    )
    parser.add_argument("--config", choices=CONFIGS, default="hybrid+rerank")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--domain", default=DEFAULT_DOMAIN)
    parser.add_argument("--no-save", action="store_true", help="ne pas écrire dans eval/results/")
    args = parser.parse_args()

    questions = load_golden(args.golden)
    conn = get_connection()

    try:
        problems = validate(questions, conn)
    finally:
        conn.close()

    if problems:
        console.print("[bold red]❌ Golden set invalide :[/bold red]")
        for problem in problems:
            console.print(f"   • {problem}")
        raise SystemExit(1)

    console.print(
        f"[bold blue]🔬 {args.golden.name}[/bold blue] — "
        f"{len(questions)} questions · {args.config} · top-{args.top_k}\n"
    )

    results: dict[str, list[str]] = {}
    start = time.perf_counter()

    for question in questions:
        found = retrieve(question["question"], args.config, args.top_k, args.domain)
        results[question["id"]] = [item["source"] for item in found]

    elapsed = time.perf_counter() - start
    metrics = evaluate(questions, results, args.top_k)

    print_report(args.config, metrics, elapsed, args.domain)

    if not args.no_save:
        output = save_result(args.config, metrics, elapsed, args.domain)
        console.print(f"\n[dim]résultat sauvegardé → {output.relative_to(Path.cwd())}[/dim]")


if __name__ == "__main__":
    main()
