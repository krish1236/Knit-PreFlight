"""Lazy-loaded local sentence-transformer for paraphrase equivalence judging.

Default model: all-MiniLM-L6-v2 (~80MB, 384-dim). Loaded once per process
on first use; subsequent calls reuse the cached model.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np

from preflight.logging import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def _load_model() -> object:
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("all-MiniLM-L6-v2")
    logger.info("embeddings.model_loaded", model="all-MiniLM-L6-v2")
    return model


def embed(texts: list[str]) -> np.ndarray:
    """Return an (n, d) array of L2-normalized embeddings."""
    model = _load_model()
    vectors = model.encode(texts, normalize_embeddings=True)  # type: ignore[attr-defined]
    return np.asarray(vectors)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two pre-normalized embedding vectors."""
    return float(np.dot(a, b))


def pairwise_cosine(matrix: np.ndarray) -> np.ndarray:
    """Pairwise cosine similarity matrix for L2-normalized rows."""
    return np.asarray(matrix @ matrix.T)
