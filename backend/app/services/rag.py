"""Minimal in-memory RAG skeleton: embed docs, retrieve top-k, then ask Claude.

Swap the in-memory store for FAISS/a vector DB once the problem statement
defines the real corpus and scale.
"""

from __future__ import annotations

import numpy as np
from sentence_transformers import SentenceTransformer

from app.services import llm

_MODEL_NAME = "all-MiniLM-L6-v2"


class SimpleRAG:
    def __init__(self, model_name: str = _MODEL_NAME) -> None:
        self._model = SentenceTransformer(model_name)
        self._docs: list[str] = []
        self._embeddings: np.ndarray | None = None

    def index(self, docs: list[str]) -> None:
        self._docs = docs
        self._embeddings = self._model.encode(docs, normalize_embeddings=True)

    def retrieve(self, query: str, top_k: int = 3) -> list[str]:
        if self._embeddings is None:
            raise RuntimeError("Call index() before retrieve()")
        query_emb = self._model.encode([query], normalize_embeddings=True)[0]
        scores = self._embeddings @ query_emb
        top_indices = np.argsort(scores)[::-1][:top_k]
        return [self._docs[i] for i in top_indices]

    def answer(self, query: str, top_k: int = 3) -> str:
        context = "\n\n".join(self.retrieve(query, top_k))
        system = (
            "Answer using only the provided context. If the answer isn't in "
            "the context, say you don't know.\n\nContext:\n" + context
        )
        return llm.chat(messages=[{"role": "user", "content": query}], system=system)
