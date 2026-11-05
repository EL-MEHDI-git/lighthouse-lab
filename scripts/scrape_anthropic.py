#!/usr/bin/env python3
"""
Script de scraping des documents Anthropic.
Récupère les articles depuis le sitemap, extrait le contenu principal
avec trafilatura (suppression nav/footer/boilerplate) et le sauvegarde en markdown.
"""
import sys
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
from datetime import datetime, timezone

import requests
import trafilatura
from bs4 import BeautifulSoup
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

console = Console()

# Configuration
SITEMAP_URL = "https://www.anthropic.com/sitemap.xml"
OUTPUT_DIR = Path("data/raw/ai_engineering")
MAX_ARTICLES = 1000            # 1000 = pas de limite pratique
REQUEST_DELAY = 0.2            # pause entre requêtes (politesse)
MIN_CONTENT_LENGTH = 200       # En dessous → page vide/index, on ignore
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; lighthouse-lab/1.0)"}


def fetch_sitemap(sitemap_url: str) -> list[dict]:
    """Récupère toutes les URLs du sitemap avec leur date de modification."""
    try:
        resp = requests.get(sitemap_url, timeout=30, headers=HEADERS)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "xml")

        entries = []
        for url in soup.find_all("url"):
            loc_tag = url.find("loc")
            if not loc_tag:
                continue

            lastmod_tag = url.find("lastmod")
            lastmod = None
            if lastmod_tag and lastmod_tag.text:
                try:
                    lastmod = datetime.fromisoformat(
                        lastmod_tag.text.replace("Z", "+00:00")
                    )
                except ValueError:
                    lastmod = None

            entries.append({"url": loc_tag.text, "lastmod": lastmod})

        return entries
    except Exception as e:
        console.print(f"[red]❌ Erreur lors du chargement du sitemap: {e}[/red]")
        return []


def filter_relevant_urls(entries: list[dict]) -> list[dict]:
    """Filtre les entrées pour ne garder que les articles pertinents."""
    relevant_patterns = ["/news/", "/engineering/", "/research/", "/announcements/"]
    return [
        e for e in entries
        if any(pattern in e["url"] for pattern in relevant_patterns)
    ]


def sort_by_newest(entries: list[dict]) -> list[dict]:
    """Trie les articles du plus récent au plus ancien (par date de modif)."""
    return sorted(
        entries,
        key=lambda e: e["lastmod"] if e["lastmod"] else datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )


def url_to_filename(url: str) -> str:
    """Convertit une URL en nom de fichier."""
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    if not path:
        return "index.md"
    return path.replace("/", "_") + ".md"


def is_already_downloaded(url: str, output_dir: Path) -> bool:
    """Vérifie si un article a déjà été téléchargé."""
    return (output_dir / url_to_filename(url)).exists()


def fetch_article_content(url: str) -> Optional[str]:
    """
    Récupère le contenu principal d'un article en Markdown,
    sans navigation, footer ni sections « Related content ».
    """
    try:
        resp = requests.get(url, timeout=30, headers=HEADERS)
        resp.raise_for_status()

        content = trafilatura.extract(
            resp.text,
            url=url,
            output_format="markdown",
            include_comments=False,
            include_tables=True,
            favor_precision=True,
            deduplicate=True,
        )
        return content if content and len(content.strip()) >= MIN_CONTENT_LENGTH else None
    except Exception as e:
        console.print(f"[yellow]⚠️  Erreur pour {url}: {e}[/yellow]")
        return None


def save_article(url: str, content: str, output_dir: Path):
    """Sauvegarde un article en fichier markdown."""
    filename = url_to_filename(url)
    filepath = output_dir / filename
    title = filename.replace(".md", "").replace("_", " ").title()

    markdown_content = f"""# {title}

Source: {url}

---

{content}
"""
    filepath.write_text(markdown_content, encoding="utf-8")


def main():
    """Pipeline de scraping principal."""
    console.print("[bold blue]🔍 Démarrage du scraping Anthropic[/bold blue]")

    # Créer le répertoire de sortie
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Étape 1: Récupérer le sitemap
    console.print("\n[bold]📥 Étape 1/4: Récupération du sitemap[/bold]")
    entries = fetch_sitemap(SITEMAP_URL)
    console.print(f"   ✅ {len(entries)} URLs trouvées")

    if not entries:
        console.print("[red]❌ Aucune URL trouvée dans le sitemap[/red]")
        sys.exit(1)

    # Étape 2: Filtrer les articles pertinents et trier du plus récent au plus ancien
    console.print("\n[bold]🔍 Étape 2/4: Filtrage et tri des articles[/bold]")
    relevant = filter_relevant_urls(entries)
    relevant = sort_by_newest(relevant)
    console.print(f"   ✅ {len(relevant)} articles pertinents trouvés")
    if relevant and relevant[0]["lastmod"]:
        console.print(f"   🗓️  Plus récent: {relevant[0]['lastmod'].date()}")

    # Étape 3: Ignorer les articles déjà téléchargés (scraping incrémental)
    console.print("\n[bold]⏭️  Étape 3/4: Détection des articles déjà téléchargés[/bold]")
    to_fetch = []
    skipped = 0
    for entry in relevant:
        if is_already_downloaded(entry["url"], OUTPUT_DIR):
            skipped += 1
        else:
            to_fetch.append(entry)
    console.print(f"   ✅ {skipped} articles déjà téléchargés (ignorés)")
    console.print(f"   ⬇️  {len(to_fetch)} articles à télécharger")

    # Limiter le nombre d'articles (le plus récent d'abord)
    if len(to_fetch) > MAX_ARTICLES:
        console.print(f"   ⚠️  Limite à {MAX_ARTICLES} articles")
        to_fetch = to_fetch[:MAX_ARTICLES]

    # Étape 4: Télécharger et sauvegarder les articles
    console.print("\n[bold]📄 Étape 4/4: Téléchargement et extraction du contenu[/bold]")

    saved_count = 0
    empty_count = 0
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Téléchargement...", total=len(to_fetch))

        for entry in to_fetch:
            url = entry["url"]
            content = fetch_article_content(url)
            if content:
                save_article(url, content, OUTPUT_DIR)
                saved_count += 1
            else:
                empty_count += 1
            progress.update(task, advance=1)
            time.sleep(REQUEST_DELAY)

    # Résumé
    console.print("\n[bold green]✅ Scraping terminé![/bold green]")
    console.print(f"   📄 Articles sauvegardés: {saved_count}")
    if empty_count:
        console.print(f"   ⚠️  Pages sans contenu exploitable: {empty_count}")
    console.print(f"   📁 Répertoire: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
