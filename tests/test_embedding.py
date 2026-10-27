from typing import Any

import numpy as np
import pytest

from tutor import config
from tutor.tools import embedding


class FakeModel:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def encode(self, texts: list[str], **options: Any) -> np.ndarray:
        self.calls.append({"texts": texts, **options})
        return np.array([[3.0, 4.0]] * len(texts), dtype=np.float64) / 5.0


def test_embed_asks_the_model_for_unit_vectors_and_returns_float32(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeModel()
    monkeypatch.setattr(embedding, "_model", lambda name: fake)
    vectors = embedding.embed(["a", "b"])
    assert vectors.shape == (2, 2) and vectors.dtype == np.float32
    assert fake.calls == [
        {
            "texts": ["a", "b"],
            "normalize_embeddings": True,
            "convert_to_numpy": True,
            "show_progress_bar": False,
        }
    ]


def test_embed_uses_the_configured_model_name(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def model(name: str) -> FakeModel:
        seen.append(name)
        return FakeModel()

    monkeypatch.setattr(embedding, "_model", model)
    monkeypatch.setattr("tutor.config.load_dotenv", lambda: False)
    monkeypatch.setenv("EMBEDDING_MODEL", "some/other-model")
    embedding.embed(["x"])
    assert seen == ["some/other-model"]


def test_the_model_name_defaults_and_can_be_overridden(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("tutor.config.load_dotenv", lambda: False)
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)
    assert config.embedding_model_name() == config.DEFAULT_EMBEDDING_MODEL
    monkeypatch.setenv("EMBEDDING_MODEL", "")
    assert config.embedding_model_name() == config.DEFAULT_EMBEDDING_MODEL
    monkeypatch.setenv("EMBEDDING_MODEL", "x/y")
    assert config.embedding_model_name() == "x/y"


def test_a_test_that_forgets_to_patch_the_model_fails_loudly() -> None:
    with pytest.raises(AssertionError, match="loaded the embedding model"):
        embedding.embed(["x"])
