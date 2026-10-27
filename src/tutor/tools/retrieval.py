"""Search the misconception catalogue for the one a wrong rewrite shows (plain numpy, no index
library).

Only the shape of what changed is compared. The two lines are trimmed of what they share at the
start and the end (the context around the error), then variables become `v` and numbers `n`: `3(x +
2) = 15 -> 3x + 2 = 15` and `5(y + 4) = 30 -> 5y + 4 = 30` have the same shape, and so does the same
slip inside a larger expression. An entry is scored by the shape of its example. The score is the
mean of two similarities between the query's shape and the entry's: plain string similarity and the
cosine similarity of their embeddings. On the dev split this beat either alone, and comparing raw
text or the descriptions was far worse (docs/decisions.md, M4b results).

Known limits of `abstract`: a product of letters (`xy`) is one name, scientific notation and
thousands separators are not understood, and unicode digits and superscripts are handled unevenly.
The catalogue examples are plain ASCII, so only the query side suffers.
"""

import re
from difflib import SequenceMatcher
from functools import lru_cache

import numpy as np
from numpy.typing import NDArray

from tutor.config import embedding_model_name
from tutor.state import CatalogueEntry, Misconception
from tutor.tools import embedding
from tutor.tools.catalogue import load_catalogue

_VARIABLE = re.compile(r"(?<![A-Za-z])[a-zA-Z](?![A-Za-z])")  # a letter on its own: not sqrt, abs
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def abstract(text: str) -> str:
    """The text with every variable replaced by `v` and every number by `n`."""
    return _NUMBER.sub("n", _VARIABLE.sub("v", text))


def trim(previous: str, written: str) -> tuple[str, str]:
    """The two lines without the start and the end they share, never cutting inside a name or
    a number."""
    limit = min(len(previous), len(written))
    start = 0
    while start < limit and previous[start] == written[start]:
        start += 1
    while (
        start > 0
        and previous[start - 1].isalnum()
        and (previous[start : start + 1].isalnum() or written[start : start + 1].isalnum())
    ):
        start -= 1
    end = 0
    while end < limit - start and previous[-1 - end] == written[-1 - end]:
        end += 1
    while (
        end > 0
        and previous[len(previous) - end].isalnum()
        and (
            previous[len(previous) - end - 1].isalnum() or written[len(written) - end - 1].isalnum()
        )
    ):
        end -= 1
    return previous[start : len(previous) - end], written[start : len(written) - end]


def shape(previous: str, written: str) -> str:
    """The shape of what changed from the line before to the line the student wrote."""
    return abstract(" -> ".join(trim(previous, written)))


def entry_shape(entry: CatalogueEntry) -> str:
    previous, written = entry.example.split(" -> ", 1)
    return shape(previous, written)


@lru_cache(maxsize=2)
def _catalogue_vectors(model_name: str) -> NDArray[np.float32]:
    """The entries' embeddings, keyed by the model so a new EMBEDDING_MODEL never reuses them."""
    return embedding.embed([entry_shape(entry) for entry in load_catalogue()])


def search(previous: str, written: str, k: int = 5) -> list[Misconception]:
    """The `k` catalogue entries whose example has the shape most like this rewrite, best first.

    The score is the mean of the string similarity and the embedding cosine, about 0 to 1.
    """
    entries = load_catalogue()
    query = shape(previous, written)
    cosine = _catalogue_vectors(embedding_model_name()) @ embedding.embed([query])[0]
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
