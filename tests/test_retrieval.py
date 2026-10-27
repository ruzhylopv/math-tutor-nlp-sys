import re
from collections.abc import Iterator, Sequence

import numpy as np
import pytest
from numpy.typing import NDArray

from tutor.tools import embedding, retrieval
from tutor.tools.catalogue import load_catalogue

DIMENSIONS = 512


def fake_embed(texts: Sequence[str]) -> NDArray[np.float32]:
    """A bag-of-words hashing embedder: similar words give similar unit vectors."""
    vectors = np.zeros((len(texts), DIMENSIONS), dtype=np.float32)
    for row, text in enumerate(texts):
        for word in re.findall(r"[a-z0-9^()+*/=-]+", text.lower()):
            vectors[row, hash(word) % DIMENSIONS] += 1.0
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.where(norms == 0, 1.0, norms)


@pytest.fixture(autouse=True)
def _fake_embedder(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(embedding, "embed", fake_embed)
    retrieval._catalogue_vectors.cache_clear()
    yield
    retrieval._catalogue_vectors.cache_clear()


def test_an_entrys_own_text_finds_that_entry_first() -> None:
    for entry in load_catalogue()[::10]:
        best = retrieval.search(retrieval.entry_text(entry), k=3)[0]
        assert best.id == entry.id
        assert best.score == pytest.approx(1.0, abs=1e-5)


def test_results_are_best_first_and_k_is_respected() -> None:
    results = retrieval.search("believes that the square of a sum is the sum of squares", k=4)
    assert len(results) == 4
    scores = [match.score for match in results]
    assert scores == sorted(scores, reverse=True)
    assert len({match.id for match in results}) == 4


def test_a_match_carries_the_catalogue_fields() -> None:
    entry = load_catalogue()[0]
    match = retrieval.search(retrieval.entry_text(entry), k=1)[0]
    assert (match.id, match.description, match.topic) == (entry.id, entry.description, entry.topic)


def test_k_larger_than_the_catalogue_returns_everything() -> None:
    assert len(retrieval.search("anything", k=10_000)) == len(load_catalogue())


def test_the_catalogue_is_embedded_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    def counting(texts: Sequence[str]) -> NDArray[np.float32]:
        calls.append(len(texts))
        return fake_embed(texts)

    monkeypatch.setattr(embedding, "embed", counting)
    retrieval._catalogue_vectors.cache_clear()
    retrieval.search("first", k=1)
    retrieval.search("second", k=1)
    assert calls == [len(load_catalogue()), 1, 1]


def test_the_embedded_text_holds_the_description_and_the_example() -> None:
    entry = load_catalogue()[0]
    text = retrieval.entry_text(entry)
    assert entry.description in text and entry.example in text
