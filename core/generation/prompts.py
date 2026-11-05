"""
Templates de prompts pour le RAG.
"""

RAG_SYSTEM_PROMPT = """You are a helpful AI assistant that answers questions based on the provided context.

Rules:
1. Only use information from the provided context to answer questions
2. If the context doesn't contain enough information, say so clearly
3. Cite your sources when possible
4. Be concise and accurate
5. If you're unsure, say "I don't have enough information to answer that question"

Context:
{context}
"""

RAG_USER_PROMPT = """Question: {question}

Please provide a clear and concise answer based on the context above."""

SUMMARY_PROMPT = """Summarize the following conversation history:

{conversation_history}

Provide a concise summary that captures the key points and context."""

CODE_ANALYSIS_PROMPT = """Analyze the following code and provide insights:

```python
{code}
```

Context: {context}

Provide:
1. Explanation of what the code does
2. Potential issues or improvements
3. Best practices recommendations
"""
