"""
Module de gestion de la mémoire de conversation.
"""
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class Message:
    """Représente un message dans la conversation."""
    role: str  # "user" ou "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)


class ConversationMemory:
    """Gestionnaire de mémoire pour les conversations."""

    def __init__(self, session_id: str, max_history: int = 20):
        """
        Initialise la mémoire de conversation.

        Args:
            session_id: Identifiant unique de la session
            max_history: Nombre maximum de messages à conserver
        """
        self.session_id = session_id
        self.max_history = max_history
        self.messages: list[Message] = []

    def add_message(self, role: str, content: str, metadata: Optional[dict] = None):
        """Ajoute un message à l'historique."""
        message = Message(
            role=role,
            content=content,
            metadata=metadata or {}
        )
        self.messages.append(message)

        # Limiter l'historique si nécessaire
        if len(self.messages) > self.max_history:
            self.messages = self.messages[-self.max_history:]

    def get_history(self, include_metadata: bool = False) -> list[dict]:
        """
        Retourne l'historique de la conversation.

        Args:
            include_metadata: Inclure les métadonnées des messages

        Returns:
            Liste des messages au format dictionnaire
        """
        history = []
        for msg in self.messages:
            entry = {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat()
            }
            if include_metadata:
                entry["metadata"] = msg.metadata
            history.append(entry)
        return history

    def get_context_string(self, max_messages: int = 10) -> str:
        """
        Retourne l'historique sous forme de string pour le contexte LLM.

        Args:
            max_messages: Nombre maximum de messages à inclure

        Returns:
            String formaté de l'historique
        """
        recent_messages = self.messages[-max_messages:]

        lines = []
        for msg in recent_messages:
            prefix = "User" if msg.role == "user" else "Assistant"
            lines.append(f"{prefix}: {msg.content}")

        return "\n".join(lines)

    def clear(self):
        """Efface l'historique de la conversation."""
        self.messages.clear()

    def get_message_count(self) -> int:
        """Retourne le nombre de messages dans l'historique."""
        return len(self.messages)