"""
Client pour interagir avec Ollama (LLM local).
"""
from typing import Optional
import ollama
from core.config import OLLAMA_HOST, LLM_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS


def get_ollama_client():
    """Retourne un client Ollama configuré."""
    return ollama.Client(host=OLLAMA_HOST)


def generate_response(
    prompt: str,
    system_prompt: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = LLM_TEMPERATURE,
    max_tokens: int = LLM_MAX_TOKENS
) -> str:
    """
    Génère une réponse avec Ollama.
    
    Args:
        prompt: Prompt utilisateur
        system_prompt: Prompt système (optionnel)
        model: Nom du modèle à utiliser
        temperature: Température pour la génération
        max_tokens: Nombre maximum de tokens
    
    Returns:
        Réponse générée
    """
    client = get_ollama_client()
    model_name = model or LLM_MODEL
    
    messages = []
    
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    
    messages.append({"role": "user", "content": prompt})
    
    try:
        response = client.chat(
            model=model_name,
            messages=messages,
            options={
                "temperature": temperature,
                "num_predict": max_tokens
            }
        )
        return response["message"]["content"]
    except Exception as e:
        raise Exception(f"Erreur lors de la génération: {e}")


def list_available_models() -> list[str]:
    """Liste les modèles disponibles dans Ollama."""
    client = get_ollama_client()
    try:
        models = client.list()
        return [model["name"] for model in models["models"]]
    except Exception:
        return []


def ensure_model_available(model_name: str) -> bool:
    """Vérifie qu'un modèle est disponible, sinon essaie de le télécharger."""
    available = list_available_models()
    
    if model_name in available:
        return True
    
    try:
        client = get_ollama_client()
        client.pull(model_name)
        return True
    except Exception:
        return False
