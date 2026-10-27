import json
from collections import Counter
from pathlib import Path
from typing import get_args

import pytest
from pydantic import ValidationError

from tutor.state import IN_SCOPE_TOPICS, CatalogueEntry, Category
from tutor.tools import catalogue
from tutor.tools.catalogue import load_catalogue


def _entry(**changes: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": "M001",
        "description": "Believes that something wrong",
        "category": "fractions",
        "topic": "Algebra",
        "correct_rule": "the right rule",
        "example": "a -> b",
    }
    return base | changes


def test_the_catalogue_loads_and_is_about_a_hundred_and_twenty_entries() -> None:
    entries = load_catalogue()
    assert 100 <= len(entries) <= 140
    assert all(isinstance(entry, CatalogueEntry) for entry in entries)


def test_ids_descriptions_and_examples_are_unique() -> None:
    entries = load_catalogue()
    for field in ("id", "description", "example"):
        values = [getattr(entry, field) for entry in entries]
        assert len(set(values)) == len(values), field


def test_every_category_is_used_with_several_entries() -> None:
    counts = Counter(entry.category for entry in load_catalogue())
    assert set(counts) == set(get_args(Category))
    assert min(counts.values()) >= 5


def test_every_topic_is_an_in_scope_subject() -> None:
    assert {entry.topic for entry in load_catalogue()} <= IN_SCOPE_TOPICS


def test_ids_are_consecutive_from_m001() -> None:
    ids = [entry.id for entry in load_catalogue()]
    assert ids == [f"M{number:03d}" for number in range(1, len(ids) + 1)]


def test_descriptions_are_written_about_the_student() -> None:
    for entry in load_catalogue():
        assert entry.description[0].isupper() and not entry.description.endswith("."), entry.id


@pytest.mark.parametrize(
    "bad",
    [
        {"id": "X1"},
        {"description": "short"},
        {"category": "geometry"},
        {"topic": "Geometry"},
        {"correct_rule": ""},
        {"example": "no arrow here"},
    ],
)
def test_an_invalid_entry_is_rejected(bad: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        CatalogueEntry.model_validate(_entry(**bad))


def test_a_duplicate_id_is_an_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "m.json"
    path.write_text(json.dumps([_entry(), _entry(description="Another wrong belief")]), "utf-8")
    monkeypatch.setattr(catalogue, "CATALOGUE_PATH", path)
    load_catalogue.cache_clear()
    try:
        with pytest.raises(ValueError, match="duplicate"):
            load_catalogue()
    finally:
        load_catalogue.cache_clear()
