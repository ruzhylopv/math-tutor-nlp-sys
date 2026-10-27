"""Search the misconception catalogue for the one a wrong rewrite shows (plain numpy, no index
library).

Only the shape of a rewrite is compared: variables become `v` and numbers `n`, so `3(x + 2) = 15 ->
3x + 2 = 15` and `5(y + 4) = 30 -> 5y + 4 = 30` have the same shape. A catalogue entry is scored by
its example's shape. The score is the mean of two similarities between the query's shape and the
entry's: plain string similarity and the cosine similarity of their embeddings. On the dev split the
mean beat either alone, and comparing raw text (or the descriptions) was far worse
(docs/decisions.md, M4b).
"""

import re
from difflib import SequenceMatcher
from functools import lru_cache

import numpy as np
from numpy.typing import NDArray

from tutor.state import CatalogueEntry, Misconception
from tutor.tools import embedding
from tutor.tools.catalogue import load_catalogue

_VARIABLE = re.compile(r"(?<![A-Za-z])[a-zA-Z](?![A-Za-z])")  # a letter on its own: not sqrt, abs
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def abstract(text: str) -> str:
    """The text with every variable replaced by `v` and every number by `n`."""
    return _NUMBER.sub("n", _VARIABLE.sub("v", text))


def shape(previous: str, written: str) -> str:
    """The shape of a rewrite from the line before to the line the student wrote."""
    return abstract(f"{previous} -> {written}")


def entry_shape(entry: CatalogueEntry) -> str:
    return abstract(entry.example)


@lru_cache(maxsize=1)
def _catalogue_vectors() -> NDArray[np.float32]:
    return embedding.embed([entry_shape(entry) for entry in load_catalogue()])


def search(previous: str, written: str, k: int = 5) -> list[Misconception]:
    """The `k` catalogue entries whose example has the shape most like this rewrite, best first.

    The score is the mean of the string similarity and the embedding cosine, about 0 to 1.
    """
    entries = load_catalogue()
    query = shape(previous, written)
    cosine = _catalogue_vectors() @ embedding.embed([query])[0]
    text = np.array(
        [
            SequenceMatcher(None, query, entry_shape(entry), autojunk=False).ratio()
            for entry in entries
        ]
    )
    scores = (cosine + text) / 2
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
