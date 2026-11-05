#!/usr/bin/env python3
"""
Script d'ingestion de documents dans la base de données.
Charge, découpe, embedde et stocke les documents.
"""
import sys
import hashlib
from pathlib import Path
from rich.console import Console

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.ingestion.loader import load_markdown_files
from core.ingestion.chunking import chunk_documents
from core.embeddings.embedder import embed_batch
from core.db.connection import get_connection, insert_chunks_batch, get_ingested_sources
from core.config import (
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    DEFAULT_DOMAIN,
)

console = Console()

DATA_DIR = Path("data/raw/ai_engineering")
DOMAIN = DEFAULT_DOMAIN


def main():
    """Pipeline d'ingestion principal."""
    console.print("[bold blue]🚀 Démarrage de l'ingestion[/bold blue]")
    
    # Vérifier que le répertoire de données existe
    if not DATA_DIR.exists():
        console.print(f"[red]❌ Répertoire non trouvé: {DATA_DIR}[/red]")
        console.print("[yellow]Exécutez d'abord le script de scraping: python scripts/scrape_anthropic.py[/yellow]")
        sys.exit(1)
    
    # Étape 1: Chargement des documents
    console.print("\n[bold]📥 Étape 1/5: Chargement des documents[/bold]")
    documents = load_markdown_files(DATA_DIR)
    console.print(f"   ✅ {len(documents)} documents chargés")
    
    if not documents:
        console.print("[red]❌ Aucun document trouvé dans le répertoire[/red]")
        sys.exit(1)
    
    # Ajouter le domaine à chaque document
    for doc in documents:
        doc["domain"] = DOMAIN
    
    # Étape 2: Ignorer les sources déjà ingérées (idempotence)
    console.print("\n[bold]🔄 Étape 2/5: Vérification des sources déjà ingérées[/bold]")
    try:
        conn = get_connection()
        ingested_sources = get_ingested_sources(conn, DOMAIN)
    except Exception as e:
        console.print(f"[red]❌ Erreur de base de données: {e}[/red]")
        console.print("[yellow]Vérifiez que PostgreSQL est démarré (docker-compose up -d)[/yellow]")
        sys.exit(1)
    
    new_documents = [d for d in documents if d["source"] not in ingested_sources]
    skipped_count = len(documents) - len(new_documents)
    console.print(f"   ✅ {skipped_count} sources déjà ingérées (ignorées)")
    console.print(f"   ⬇️  {len(new_documents)} nouvelles sources à traiter")
    
    if not new_documents:
        console.print("\n[bold green]✅ Rien à faire: tous les documents sont déjà ingérés![/bold green]")
        conn.close()
        sys.exit(0)
    
    # Étape 3: Découpage en chunks
    console.print("\n[bold]✂️  Étape 3/5: Découpage en chunks[/bold]")
    chunks = chunk_documents(new_documents, CHUNK_SIZE, CHUNK_OVERLAP)
    console.print(f"   ✅ {len(chunks)} chunks créés (taille: {CHUNK_SIZE}, chevauchement: {CHUNK_OVERLAP})")

    # Déduplication globale: même contenu = un seul chunk en base
    seen_hashes = set()
    unique_chunks = []
    duplicates = 0
    for chunk in chunks:
        content_hash = hashlib.md5(chunk["content"].encode("utf-8")).hexdigest()
        if content_hash in seen_hashes:
            duplicates += 1
            continue
        seen_hashes.add(content_hash)
        unique_chunks.append(chunk)
    chunks = unique_chunks
    console.print(f"   🧹 {duplicates} chunks dupliqués supprimés → {len(chunks)} chunks uniques")
    
    # Étape 4: Génération des embeddings
    console.print("\n[bold]🧠 Étape 4/5: Génération des embeddings[/bold]")
    texts = [chunk["content"] for chunk in chunks]
    embeddings = embed_batch(texts, show_progress=True)
    console.print(f"   ✅ {len(embeddings)} embeddings générés")
    
    # Étape 5: Insertion dans la base de données
    console.print("\n[bold]💾 Étape 5/5: Insertion dans la base de données[/bold]")
    try:
        inserted_ids = insert_chunks_batch(conn, chunks, embeddings)
        conn.commit()
        console.print(f"   ✅ {len(inserted_ids)} chunks insérés dans la base de données")
    except Exception as e:
        console.print(f"[red]❌ Erreur de base de données: {e}[/red]")
        console.print("[yellow]Vérifiez que PostgreSQL est démarré (docker-compose up -d)[/yellow]")
        sys.exit(1)
    finally:
        conn.close()
    
    # Résumé
    console.print("\n[bold green]✅ Ingestion terminée avec succès![/bold green]")
    console.print(f"   📄 Documents traités: {len(new_documents)}")
    console.print(f"   🧩 Chunks: {len(chunks)}")
    console.print(f"   🔢 Embeddings: {len(embeddings)}")


if __name__ == "__main__":
    main()
