"""Search the misconception catalogue by embedding similarity (plain numpy, no index library)."""

from functools import lru_cache

import numpy as np
from numpy.typing import NDArray

from tutor.state import CatalogueEntry, Misconception
from tutor.tools import embedding
from tutor.tools.catalogue import load_catalogue


def entry_text(entry: CatalogueEntry) -> str:
    """What is embedded for an entry: the description and its example wrong rewrite."""
    return f"{entry.description}. Example: {entry.example}"


@lru_cache(maxsize=1)
def _catalogue_vectors() -> NDArray[np.float32]:
    return embedding.embed([entry_text(entry) for entry in load_catalogue()])


def search(query: str, k: int = 5) -> list[Misconception]:
    """The `k` catalogue entries most similar to the query, best first, with the cosine score."""
    entries = load_catalogue()
    scores = _catalogue_vectors() @ embedding.embed([query])[0]
    order = np.argsort(-scores, kind="stable")[:k]
    return [
        Misconception(
            id=entries[i].id,
            description=entries[i].description,
            topic=entries[i].topic,
            score=float(scores[i]),
        )
        for i in order
    ]
