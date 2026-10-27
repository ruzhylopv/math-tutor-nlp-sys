from collections.abc import Iterator, Sequence

import numpy as np
import pytest
from numpy.typing import NDArray

from tutor.tools import embedding, retrieval
from tutor.tools.catalogue import load_catalogue

DIMENSIONS = 512


def fake_embed(texts: Sequence[str]) -> NDArray[np.float32]:
    """A bag-of-characters embedder: similar strings give similar unit vectors."""
    vectors = np.zeros((len(texts), DIMENSIONS), dtype=np.float32)
    for row, text in enumerate(texts):
        for left, right in zip(text, text[1:], strict=False):
            vectors[row, (ord(left) * 31 + ord(right)) % DIMENSIONS] += 1.0
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.where(norms == 0, 1.0, norms)


@pytest.fixture(autouse=True)
def _fake_embedder(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(embedding, "embed", fake_embed)
    retrieval._catalogue_vectors.cache_clear()
    yield
    retrieval._catalogue_vectors.cache_clear()


@pytest.mark.parametrize(
    ("text", "shape"),
    [
        ("3(x + 2) = 15", "n(v + n) = n"),
        ("5(y + 4) = 30", "n(v + n) = n"),
        ("2x + 3.5", "nv + n"),
        ("sqrt(x + 7) = x - 5", "sqrt(v + n) = v - n"),
        ("abs(n) + 1/2", "abs(v) + n/n"),
        ("x^2 - 9", "v^n - n"),
    ],
)
def test_abstract_keeps_the_shape_and_drops_the_names_and_values(text: str, shape: str) -> None:
    assert retrieval.abstract(text) == shape


def test_numbers_and_variables_stay_apart() -> None:
    assert retrieval.abstract("n + 2") == "v + n"  # a variable called n is still a variable


def test_a_rewrite_with_other_numbers_and_letters_has_the_same_shape() -> None:
    assert retrieval.shape("3(x + 2) = 15", "3x + 2 = 15") == retrieval.shape(
        "8(t + 5) = 90", "8t + 5 = 90"
    )


def test_an_entrys_own_example_finds_an_entry_with_that_shape() -> None:
    entries = load_catalogue()
    for entry in entries[::7]:
        previous, written = entry.example.split(" -> ")
        best = retrieval.search(previous, written, k=3)[0]
        by_id = {e.id: e for e in entries}
        assert retrieval.entry_shape(by_id[best.id]) == retrieval.entry_shape(entry)


def test_results_are_best_first_and_k_is_respected() -> None:
    results = retrieval.search("(x + 3)^2", "x^2 + 9", k=4)
    assert len(results) == 4
    scores = [match.score for match in results]
    assert scores == sorted(scores, reverse=True)
    assert len({match.id for match in results}) == 4


def test_the_score_is_the_mean_of_string_and_embedding_similarity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        embedding, "embed", lambda texts: np.ones((len(texts), 2), np.float32) / 2**0.5
    )
    retrieval._catalogue_vectors.cache_clear()
    entry = load_catalogue()[0]
    previous, written = entry.example.split(" -> ")
    best = retrieval.search(previous, written, k=1)[0]
    assert best.id == entry.id
    assert best.score == pytest.approx((1.0 + 1.0) / 2)  # identical shape: ratio 1, cosine 1


def test_the_string_similarity_decides_when_the_embedder_cannot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        embedding, "embed", lambda texts: np.ones((len(texts), 2), np.float32) / 2**0.5
    )
    retrieval._catalogue_vectors.cache_clear()
    entry = load_catalogue()[40]
    previous, written = entry.example.split(" -> ")
    assert retrieval.search(previous, written, k=1)[0].id == entry.id


def test_a_match_carries_the_catalogue_fields() -> None:
    entry = load_catalogue()[0]
    previous, written = entry.example.split(" -> ")
    match = retrieval.search(previous, written, k=1)[0]
    assert (match.description, match.topic) == (entry.description, entry.topic)


def test_k_larger_than_the_catalogue_returns_everything() -> None:
    assert len(retrieval.search("a", "b", k=10_000)) == len(load_catalogue())


def test_the_catalogue_is_embedded_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    def counting(texts: Sequence[str]) -> NDArray[np.float32]:
        calls.append(len(texts))
        return fake_embed(texts)

    monkeypatch.setattr(embedding, "embed", counting)
    retrieval._catalogue_vectors.cache_clear()
    retrieval.search("a", "b", k=1)
    retrieval.search("c", "d", k=1)
    assert calls == [len(load_catalogue()), 1, 1]


@pytest.mark.parametrize(
    ("previous", "written", "trimmed"),
    [
        ("3(x + 2) = 15", "3x + 2 = 15", ("3(x + 2)", "3x + 2")),
        ("7 + (3(x + 2))", "7 + (3x + 2)", ("3(x + 2)", "3x + 2")),
        ("12 + 5", "13 + 5", ("12", "13")),  # never cuts inside a number
        ("ab + 1", "ac + 1", ("ab", "ac")),  # nor inside a name
        ("x + 5 = 12", "x = 12 + 5", ("+ 5 = 12", "= 12 + 5")),
        ("2 + 2", "2 + 2", ("", "")),
        ("abc", "xyz", ("abc", "xyz")),
    ],
)
def test_trim_drops_what_the_two_lines_share_at_the_ends(
    previous: str, written: str, trimmed: tuple[str, str]
) -> None:
    assert retrieval.trim(previous, written) == trimmed


def test_the_same_slip_inside_a_larger_expression_has_the_same_shape() -> None:
    plain = retrieval.shape("3(x + 2)", "3x + 2")
    assert retrieval.shape("7 + (3(x + 2))", "7 + (3x + 2)") == plain
    assert retrieval.shape("3(x + 2) + 9 = 9 + 15", "3x + 2 + 9 = 9 + 15") == plain


def test_the_catalogue_vectors_are_kept_per_embedding_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    def counting(texts: Sequence[str]) -> NDArray[np.float32]:
        calls.append(len(texts))
        return fake_embed(texts)

    monkeypatch.setattr(embedding, "embed", counting)
    monkeypatch.setattr("tutor.config.load_dotenv", lambda: False)
    monkeypatch.setenv("EMBEDDING_MODEL", "model/a")
    retrieval.search("a", "b", k=1)
    monkeypatch.setenv("EMBEDDING_MODEL", "model/b")
    retrieval.search("a", "b", k=1)
    monkeypatch.setenv("EMBEDDING_MODEL", "model/a")
    retrieval.search("a", "b", k=1)
    size = len(load_catalogue())
    assert calls == [size, 1, size, 1, 1]  # the vectors of model/a were kept, not recomputed
