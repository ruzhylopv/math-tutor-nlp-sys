"""Turn texts into unit vectors with a sentence-transformers model.

The model (EMBEDDING_MODEL, see `tutor.config`) is downloaded from the Hugging Face Hub on first use
and kept in memory. Unit tests never load it: they patch `embed` (or `_model`).
"""

from collections.abc import Sequence
from functools import lru_cache
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from tutor.config import embedding_model_name

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


@lru_cache(maxsize=2)
def _model(name: str) -> "SentenceTransformer":
    from sentence_transformers import SentenceTransformer  # slow import (PyTorch), so only here

    return SentenceTransformer(name)


def embed(texts: Sequence[str]) -> NDArray[np.float32]:
    """One unit-length row per text, so a dot product is the cosine similarity."""
    vectors = _model(embedding_model_name()).encode(
        list(texts), normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False
    )
    return np.asarray(vectors, dtype=np.float32)
