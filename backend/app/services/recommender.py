"""Skeleton content-based recommender using TF-IDF cosine similarity.

Swap the internals for collaborative/hybrid filtering once the problem
statement defines the real item catalog and interaction data.
"""

from __future__ import annotations

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class ContentRecommender:
    def __init__(self) -> None:
        self._vectorizer = TfidfVectorizer(stop_words="english")
        self._matrix = None
        self._items: pd.DataFrame | None = None

    def fit(self, items: pd.DataFrame, text_column: str) -> None:
        self._items = items.reset_index(drop=True)
        self._matrix = self._vectorizer.fit_transform(self._items[text_column].fillna(""))

    def recommend(self, item_id: int, id_column: str, top_k: int = 5) -> pd.DataFrame:
        if self._items is None or self._matrix is None:
            raise RuntimeError("Call fit() before recommend()")
        idx = self._items.index[self._items[id_column] == item_id][0]
        scores = cosine_similarity(self._matrix[idx], self._matrix).flatten()
        top_indices = scores.argsort()[::-1]
        top_indices = [i for i in top_indices if i != idx][:top_k]
        return self._items.iloc[top_indices]
