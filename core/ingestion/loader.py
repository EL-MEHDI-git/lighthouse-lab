from pathlib import Path


def load_markdown_files(directory: Path) -> list[dict]:
    """Charge tous les .md d'un dossier et retourne leur contenu."""
    documents = []
    for filepath in directory.glob("*.md"):
        content = filepath.read_text(encoding="utf-8")
        documents.append({
            "source": filepath.name,
            "content": content
        })
    return documents


def load_all_documents(directory: Path) -> list[dict]:
    """Charge tous les documents supportés d'un dossier."""
    documents = []
    supported_extensions = {".md", ".txt", ".rst"}
    
    for filepath in directory.rglob("*"):
        if filepath.suffix.lower() in supported_extensions:
            try:
                content = filepath.read_text(encoding="utf-8")
                documents.append({
                    "source": str(filepath.relative_to(directory)),
                    "content": content
                })
            except Exception as e:
                print(f"Error reading {filepath}: {e}")
    
    return documents
