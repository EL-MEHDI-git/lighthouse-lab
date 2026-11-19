"""Local HTTP entry point for the Lighthouse workspace."""

import logging
from uuid import UUID

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from core.rag.pipeline import RAGPipeline

logger = logging.getLogger(__name__)
app = FastAPI(title="Lighthouse Lab")
pipeline = RAGPipeline()


class AskRequest(BaseModel):
    question: str = Field(max_length=4000)
    session_id: UUID


class Passage(BaseModel):
    id: int
    source: str | None
    content: str


class AskResponse(BaseModel):
    answer: str
    sources: list[Passage]


@app.post("/api/ask")
def ask(request: AskRequest) -> AskResponse:
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Saisis une question.")

    try:
        result = pipeline.ask(question, session_id=str(request.session_id))
    except Exception:
        logger.exception("RAG query failed")
        raise HTTPException(
            status_code=503,
            detail="Le chatbot ne répond pas. Vérifie PostgreSQL, Ollama et le terminal de l’API.",
        ) from None

    return AskResponse(
        answer=result["answer"],
        sources=[Passage(**source) for source in result["sources"]],
    )
