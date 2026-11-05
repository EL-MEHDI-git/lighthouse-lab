#!/usr/bin/env python3
"""
Script de test pour le pipeline RAG.
Pose des questions et affiche les réponses.
"""
import sys
from pathlib import Path
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.rag.pipeline import RAGPipeline

console = Console()


def main():
    """Test du pipeline RAG."""
    console.print("[bold blue]🤖 Test du Pipeline RAG[/bold blue]\n")
    
    # Initialiser le pipeline
    try:
        pipeline = RAGPipeline()
        console.print("[green]✅ Pipeline initialisé[/green]\n")
    except Exception as e:
        console.print(f"[red]❌ Erreur d'initialisation: {e}[/red]")
        console.print("[yellow]Vérifiez que Ollama est démarré (ollama serve)[/yellow]")
        sys.exit(1)
    
    # Mode interactif
    console.print("\n[bold blue]💬 Mode interactif[/bold blue]")
    console.print("Tapez 'quit' pour quitter, 'clear' pour effacer l'historique\n")
    
    session_id = "interactive"
    
    while True:
        try:
            question = input("❓ Votre question: ").strip()
            
            if question.lower() == 'quit':
                console.print("[yellow]👋 Au revoir![/yellow]")
                break
            
            if question.lower() == 'clear':
                pipeline.clear_session(session_id)
                console.print("[green]🗑️  Historique effacé[/green]")
                continue
            
            if not question:
                continue
            
            result = pipeline.ask(question, session_id=session_id)
            
            console.print("\n[bold green]📝 Réponse:[/bold green]")
            console.print(Panel(result["answer"], border_style="green"))
            
            if result["sources"]:
                console.print("\n[bold]📚 Sources:[/bold]")
                for source in result["sources"]:
                    console.print(f"  • {source['source']} (similarité: {source['similarity']:.2f})")
            
            console.print()
            
        except KeyboardInterrupt:
            console.print("\n[yellow]👋 Au revoir![/yellow]")
            break
        except Exception as e:
            console.print(f"[red]❌ Erreur: {e}[/red]")


if __name__ == "__main__":
    main()
