"""
Pipeline RAG complet: Retrieval-Augmented Generation.
Orchestre la recherche, la génération et la mémoire.
"""
from typing import Optional
from core.config import (
    TOP_K,
    MAX_CONTEXT_LENGTH,
    LLM_MODEL,
    DEFAULT_DOMAIN,
)
from core.retrieval.vector_search import get_context_for_query, vector_search
from core.generation.llm_client import generate_response
from core.generation.prompts import RAG_SYSTEM_PROMPT, RAG_USER_PROMPT
from core.memory.conversation import ConversationMemory


class RAGPipeline:
    """Pipeline RAG complet pour le questionnement."""
    
    def __init__(
        self,
        model: Optional[str] = LLM_MODEL,
        top_k: int = TOP_K,
        max_context_length: int = MAX_CONTEXT_LENGTH,
        temperature: float = 0.7,
        domain: Optional[str] = DEFAULT_DOMAIN
    ):
        """
        Initialise le pipeline RAG.
        
        Args:
            model: Modèle LLM à utiliser
            top_k: Nombre de chunks à récupérer
            max_context_length: Longueur maximale du contexte
            temperature: Température pour la génération
            domain: Domaine à interroger (None = tous)
        """
        self.model = model
        self.top_k = top_k
        self.max_context_length = max_context_length
        self.temperature = temperature
        self.domain = domain
        self.conversations: dict[str, ConversationMemory] = {}
    
    def get_or_create_conversation(self, session_id: str) -> ConversationMemory:
        """Récupère ou crée une mémoire de conversation."""
        if session_id not in self.conversations:
            self.conversations[session_id] = ConversationMemory(session_id)
        return self.conversations[session_id]
    
    def ask(
        self,
        question: str,
        session_id: str = "default",
        include_history: bool = True
    ) -> dict:
        """
        Pose une question au pipeline RAG.
        
        Args:
            question: Question à poser
            session_id: Identifiant de la session
            include_history: Inclure l'historique dans le contexte
        
        Returns:
            Dictionnaire avec la réponse, le contexte et les sources
        """
        # Récupérer ou créer la mémoire de conversation
        memory = self.get_or_create_conversation(session_id)
        
        # Récupérer le contexte pertinent
        context = get_context_for_query(question, self.top_k, self.max_context_length, self.domain)
        
        # Construire le prompt avec l'historique si nécessaire
        user_prompt = RAG_USER_PROMPT.format(question=question)
        
        if include_history and memory.get_message_count() > 0:
            history_context = memory.get_context_string(max_messages=5)
            user_prompt = f"Conversation history:\n{history_context}\n\n{user_prompt}"
        
        # Construire le prompt système avec le contexte
        system_prompt = RAG_SYSTEM_PROMPT.format(context=context)
        
        # Générer la réponse
        response = generate_response(
            prompt=user_prompt,
            system_prompt=system_prompt,
            model=self.model,
            temperature=self.temperature
        )
        
        # Sauvegarder dans la mémoire
        memory.add_message("user", question)
        memory.add_message("assistant", response, {"context": context})
        
        # Récupérer les sources
        sources = vector_search(question, self.top_k, self.domain)
        
        return {
            "answer": response,
            "context": context,
            "sources": sources,
            "session_id": session_id
        }
    
    def clear_session(self, session_id: str):
        """Efface l'historique d'une session."""
        if session_id in self.conversations:
            self.conversations[session_id].clear()
    
    def get_session_history(self, session_id: str) -> list[dict]:
        """Retourne l'historique d'une session."""
        if session_id in self.conversations:
            return self.conversations[session_id].get_history()
        return []
